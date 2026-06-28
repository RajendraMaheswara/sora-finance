from flask import Flask, request, jsonify
from config import Config
import os
import traceback
import uuid
import threading
import sys
import asyncio
from datetime import datetime, date

from modules.visitors.forecaster import forecast_service as visitors_forecast_service
from modules.visitors.trainer import trainer as visitors_trainer
from modules.visitors.forecaster import golang_client

# Import modul inventory
from modules.inventory.forecaster import InventoryForecaster
from modules.inventory.trainer import train_all_inventory_models, training_tasks

# Import modul Sales
from modules.sales.forecaster import sales_forecast_service
from modules.sales.trainer import trainer as sales_trainer

sales_training_tasks = {}

def background_sales_training(task_id):
    try:
        sales_training_tasks[task_id]["status"] = "TRAINING"
        sales_training_tasks[task_id]["message"] = "Proses training sales sedang berjalan..."
        # Legacy compatibility
        sales_training_tasks[task_id]["status"] = "COMPLETED"
        sales_training_tasks[task_id]["message"] = "Training Sales selesai."
    except Exception as e:
        traceback.print_exc()
        sales_training_tasks[task_id]["status"] = "ERROR"
        sales_training_tasks[task_id]["message"] = str(e)

def _map_horizon_to_freq(horizon_label):
    mapping = {'daily': 'D', 'weekly': 'W', 'monthly': 'M'}
    freq = mapping.get(horizon_label.lower())
    if not freq:
        raise ValueError("horizon_label harus daily/weekly/monthly")
    return freq

# Scheduler visitors otomatis
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import logging

logger = logging.getLogger("forecast_service")
logger.setLevel(getattr(logging, str(getattr(Config, "LOG_LEVEL", "INFO")).upper(), logging.INFO))
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
    logger.addHandler(handler)

app = Flask(__name__)

@app.before_request
def check_internal_service_key():
    if request.method == "OPTIONS":
        return
    # Hanya berlakukan untuk endpoint sales dan inventory
    if request.path.startswith("/api/forecast/"):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"detail": "Missing or invalid internal service key (Bearer token)"}), 401
        
        token = auth_header.split(" ")[1]
        if token != Config.INTERNAL_SERVICE_KEY:
            return jsonify({"detail": "Unauthorized internal service key"}), 401


# ============================================
# VISITORS SCHEDULER
# ============================================
# In-memory guard agar job yang sama tidak dieksekusi berkali-kali dalam satu
# process karena scheduler check berjalan tiap N menit. Persistensi idempotency
# tetap sebaiknya ditambahkan di backend jika nanti service berjalan multi-process.
_VISITORS_SCHEDULER_RUN_KEYS = set()
_VISITORS_SCHEDULER_RUNNING_KEYS = set()
_VISITORS_SCHEDULER_LOCK = threading.Lock()


def _visitors_scheduler_key(job):
    start_date = job.get("start_date")
    if isinstance(start_date, date):
        start_value = start_date.isoformat()
    else:
        start_value = str(start_date)
    return (str(job.get("store_id")), str(job.get("horizon_label")), start_value)


async def _run_visitors_scheduler_once_async():
    """Cek semua store dan jalankan visitors forecast yang sudah due."""
    store_ids = await golang_client.fetch_store_ids()
    if not store_ids:
        logger.warning("Visitors scheduler: tidak ada store dari backend internal /stores")
        return []

    results = []
    for store_id in store_ids:
        try:
            operational_hours = await golang_client.fetch_store_operational_hours(store_id)
            jobs = visitors_forecast_service.build_scheduler_jobs_for_store(
                store_id=store_id,
                operational_hours=operational_hours,
            )

            due_jobs = []
            for job in jobs:
                key = _visitors_scheduler_key(job)
                with _VISITORS_SCHEDULER_LOCK:
                    if key in _VISITORS_SCHEDULER_RUN_KEYS or key in _VISITORS_SCHEDULER_RUNNING_KEYS:
                        continue
                    _VISITORS_SCHEDULER_RUNNING_KEYS.add(key)
                due_jobs.append((key, job))

            if not due_jobs:
                continue

            if Config.SCHEDULER_RETRAIN:
                logger.info("Visitors scheduler: retrain store=%s sebelum auto forecast", store_id)
                await visitors_forecast_service.retrain(store_id=store_id, force=True)

            for key, job in due_jobs:
                try:
                    logger.info(
                        "Visitors scheduler: run store=%s horizon=%s start_date=%s",
                        store_id,
                        job["horizon_label"],
                        job["start_date"],
                    )
                    forecast_result = await visitors_forecast_service.forecast_by_horizon(
                        store_id=store_id,
                        horizon_label=job["horizon_label"],
                        horizon_count=job["horizon_count"],
                        start_date=job["start_date"],
                    )

                    # Preserve scheduler metadata di response/save summary. Forecast dipanggil
                    # dengan explicit start_date agar period boundary pasti, tapi source-nya
                    # tetap scheduler, bukan manual user body.
                    if hasattr(forecast_result, "start_date_source"):
                        forecast_result.start_date_source = job.get("start_date_source")
                    if hasattr(forecast_result, "business_cutoff_rule"):
                        forecast_result.business_cutoff_rule = job.get("business_cutoff_rule")
                    if hasattr(forecast_result, "last_actual_date"):
                        forecast_result.last_actual_date = job.get("latest_complete_day")

                    save_result = visitors_forecast_service.save_forecast_result(
                        forecast_response=forecast_result,
                        horizon_label=job["horizon_label"],
                        horizon_count=job["horizon_count"],
                    )
                    with _VISITORS_SCHEDULER_LOCK:
                        _VISITORS_SCHEDULER_RUN_KEYS.add(key)
                    results.append({
                        "store_id": store_id,
                        "horizon_label": job["horizon_label"],
                        "start_date": job["start_date"].isoformat() if isinstance(job["start_date"], date) else job["start_date"],
                        "run_id": save_result.get("run_id"),
                        "saved_results": save_result.get("saved_results"),
                    })
                except Exception:
                    traceback.print_exc()
                finally:
                    with _VISITORS_SCHEDULER_LOCK:
                        _VISITORS_SCHEDULER_RUNNING_KEYS.discard(key)
        except Exception:
            traceback.print_exc()

    if results:
        logger.info("Visitors scheduler selesai: %s job tersimpan", len(results))
    return results


def scheduled_visitors_forecast_check():
    try:
        asyncio.run(_run_visitors_scheduler_once_async())
    except Exception:
        traceback.print_exc()


scheduler = None
if Config.FORECAST_MODE == "scheduler":
    scheduler = BackgroundScheduler(timezone=Config.FORECAST_SCHEDULER_TIMEZONE)
    scheduler.add_job(
        func=scheduled_visitors_forecast_check,
        trigger="interval",
        minutes=Config.FORECAST_SCHEDULER_CHECK_INTERVAL_MINUTES,
        id="visitors_auto_forecast_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
    logger.info(
        "Visitors scheduler enabled: interval=%s minutes, after_close=%s minutes, 24h_cutoff=%s minutes, retrain=%s",
        Config.FORECAST_SCHEDULER_CHECK_INTERVAL_MINUTES,
        Config.FORECAST_AFTER_CLOSE_SCHEDULER_MINUTES,
        Config.FORECAST_24H_RUN_SCHEDULER_MINUTES,
        Config.SCHEDULER_RETRAIN,
    )
else:
    logger.info("Visitors scheduler disabled because FORECAST_MODE=%s", Config.FORECAST_MODE)

# ============================================
# ROUTE MODUL VISITORS
# ============================================

@app.route('/health', methods=['GET'])
def health_check():
    golang_reachable = asyncio.run(golang_client.is_reachable())
    loaded_models = visitors_trainer.list_trained_stores()
    return jsonify({
        "status": "healthy" if golang_reachable else "degraded",
        "service": "sora-forecast-service",
        "version": "1.0.0",
        "golang_api_reachable": golang_reachable,
        "loaded_models": loaded_models,
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route('/api/forecast/visitors/models', methods=['GET'])
def visitors_list_models():
    stores = visitors_trainer.list_trained_stores()
    return jsonify({
        "status": "success",
        "trained_store_count": len(stores),
        "store_ids": stores,
    }), 200

@app.route('/api/forecast/visitors/retrain', methods=['POST'])
def visitors_retrain():
    req = request.get_json()
    if not req or 'store_id' not in req:
        return jsonify({"detail": "store_id wajib diisi"}), 400
    
    store_id = req['store_id']
    force = req.get('force', False)

    try:
        result = asyncio.run(visitors_forecast_service.retrain(
            store_id=store_id,
            force=force
        ))
        return jsonify(_json_model(result)), 200
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Retrain gagal: {str(e)}"}), 500

VALID_VISITORS_HORIZONS = {"daily", "weekly", "monthly"}


def _parse_visitors_standard_body():
    req = request.get_json(silent=True) or {}

    store_id = req.get("store_id")
    if not store_id:
        return None, ({"detail": "store_id wajib diisi"}, 400)

    horizon_label = req.get("horizon_label")
    if horizon_label not in VALID_VISITORS_HORIZONS:
        return None, ({"detail": "horizon_label harus daily, weekly, atau monthly"}, 400)

    try:
        horizon_count = int(req.get("horizon_count"))
    except (TypeError, ValueError):
        return None, ({"detail": "horizon_count wajib berupa angka"}, 400)

    if horizon_count <= 0:
        return None, ({"detail": "horizon_count harus lebih besar dari 0"}, 400)

    start_date = None
    start_date_str = req.get("start_date")
    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            return None, ({"detail": "start_date harus format YYYY-MM-DD"}, 400)

    return {
        "store_id": store_id,
        "horizon_label": horizon_label,
        "horizon_count": horizon_count,
        "start_date": start_date,
    }, None


def _json_model(result):
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if hasattr(result, "json"):
        import json as _json
        return _json.loads(result.json())
    if hasattr(result, "dict"):
        return result.dict()
    return result


def _date_or_none(value):
    return value.isoformat() if isinstance(value, date) else None


def _visitors_request_meta(payload):
    return {
        "store_id": payload["store_id"],
        "horizon_label": payload["horizon_label"],
        "horizon_count": payload["horizon_count"],
        "start_date": _date_or_none(payload.get("start_date")),
        "start_date_mode": "manual" if payload.get("start_date") else "auto",
    }


def _parse_iso_date(value):
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _days_between(start_value, end_value):
    start = _parse_iso_date(start_value)
    end = _parse_iso_date(end_value)
    if not start or not end:
        return None
    return (end - start).days + 1


def _clean_visitors_forecast_item(item, horizon_label):
    """Format item forecast visitors untuk response client.

    predicted_transactions sengaja tidak dikirim karena nilainya sama dengan
    predicted_visitors dan membuat response visitors ambigu.
    """
    if horizon_label == "daily":
        cleaned = {
            "date": item.get("date"),
            "predicted_visitors": item.get("predicted_visitors"),
            "lower_bound": item.get("lower_bound"),
            "upper_bound": item.get("upper_bound"),
            "day_of_week": item.get("day_of_week"),
            "is_weekend": item.get("is_weekend"),
        }
    elif horizon_label == "weekly":
        cleaned = {
            "period_start": item.get("period_start"),
            "period_end": item.get("period_end"),
            "predicted_visitors": item.get("predicted_visitors"),
            "lower_bound": item.get("lower_bound"),
            "upper_bound": item.get("upper_bound"),
        }
    else:
        cleaned = {
            "period_start": item.get("period_start"),
            "period_end": item.get("period_end"),
            "predicted_visitors": item.get("predicted_visitors"),
            "lower_bound": item.get("lower_bound"),
            "upper_bound": item.get("upper_bound"),
        }

    return {key: value for key, value in cleaned.items() if value is not None}


def _visitors_model_metadata_public(raw_metadata, horizon_label, save_result=None):
    raw_metadata = raw_metadata or {}
    model_metrics = raw_metadata.get("metrics") or {}
    save_metrics = (save_result or {}).get("metrics") or {}

    metadata = {
        "trained_at": raw_metadata.get("trained_at"),
        "training_data_points": raw_metadata.get("training_data_points"),
        "metric_horizon": raw_metadata.get("metric_horizon") or horizon_label,
        "horizon_method": raw_metadata.get("horizon_method"),
        # Nama cv_mae/cv_rmse dipertahankan sesuai permintaan.
        "cv_mae": raw_metadata.get("cv_mae"),
        "cv_rmse": raw_metadata.get("cv_rmse"),
        "error_ratio": model_metrics.get(f"{horizon_label}_error_ratio"),
        "wape": model_metrics.get(f"{horizon_label}_wape"),
        "error_percentage": model_metrics.get(f"{horizon_label}_error_percentage") or model_metrics.get(f"{horizon_label}_mae_percentage"),
        "bias": model_metrics.get(f"{horizon_label}_bias"),
        "mean_error": model_metrics.get(f"{horizon_label}_mean_error"),
        "bias_percentage": model_metrics.get(f"{horizon_label}_bias_percentage"),
        "interval_coverage": model_metrics.get(f"{horizon_label}_interval_coverage"),
        "avg_interval_width": model_metrics.get(f"{horizon_label}_avg_interval_width"),
        "relative_interval_width": model_metrics.get(f"{horizon_label}_relative_interval_width"),
        "reliability": model_metrics.get(f"{horizon_label}_reliability"),
        "confidence_level": save_metrics.get("confidence_level"),
        "metrics_version": model_metrics.get("metrics_version"),
        "metric_source": model_metrics.get("metric_source"),
        "feature_importance": raw_metadata.get("feature_importance") or {},
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _visitors_save_result_public(save_result):
    if not save_result:
        return None
    return {
        "run_id": save_result.get("run_id"),
        "saved_results": save_result.get("saved_results"),
        "status": "saved",
    }


def _visitors_response_data_public(forecast_result, payload, save_result=None):
    raw = _json_model(forecast_result)
    horizon_label = payload["horizon_label"]
    horizon_count = payload["horizon_count"]

    forecasts = [
        _clean_visitors_forecast_item(item, horizon_label)
        for item in raw.get("forecasts", [])
    ]
    total_predicted = int(sum(float(item.get("predicted_visitors") or 0) for item in forecasts))
    forecast_count = len(forecasts)
    avg_predicted = round(total_predicted / forecast_count, 2) if forecast_count else 0

    forecast_start = raw.get("forecast_start_date")
    forecast_end = raw.get("forecast_end_date")
    horizon_days = _days_between(forecast_start, forecast_end)
    if horizon_days is None:
        horizon_days = raw.get("forecast_horizon_days")
        if horizon_days is None and save_result:
            horizon_days = save_result.get("horizon_days")

    return {
        "store_id": raw.get("store_id"),
        "generated_at": raw.get("generated_at"),
        "forecast_start_date": forecast_start,
        "forecast_end_date": forecast_end,
        "horizon": {
            "label": horizon_label,
            "count": horizon_count,
            "days": horizon_days,
        },
        "start_date_source": raw.get("start_date_source"),
        "last_actual_date": raw.get("last_actual_date"),
        "business_cutoff_rule": raw.get("business_cutoff_rule"),
        "summary": {
            "total_predicted_visitors": total_predicted,
            "average_predicted_visitors": avg_predicted,
            "forecast_count": forecast_count,
        },
        "forecasts": forecasts,
        "model_metadata": _visitors_model_metadata_public(
            raw.get("model_metadata"),
            horizon_label,
            save_result=save_result,
        ),
    }


def _run_visitors_preview(payload):
    return asyncio.run(visitors_forecast_service.forecast_by_horizon(
        store_id=payload["store_id"],
        horizon_label=payload["horizon_label"],
        horizon_count=payload["horizon_count"],
        start_date=payload["start_date"],
    ))


def _handle_visitors_standard_error(exc, prefix="Internal server error"):
    if isinstance(exc, FileNotFoundError):
        return jsonify({"detail": str(exc)}), 404
    if isinstance(exc, ValueError):
        return jsonify({"detail": str(exc)}), 400
    traceback.print_exc()
    return jsonify({"detail": f"{prefix}: {str(exc)}"}), 500


@app.route('/api/forecast/visitors/preview', methods=['POST'])
def visitors_preview_standard():
    payload, error = _parse_visitors_standard_body()
    if error:
        body, status = error
        return jsonify(body), status

    try:
        result = _run_visitors_preview(payload)
        return jsonify({
            "status": "success",
            "message": "Forecast visitors berhasil dibuat tanpa disimpan.",
            "request": _visitors_request_meta(payload),
            "data": _visitors_response_data_public(result, payload),
        }), 200
    except Exception as exc:
        return _handle_visitors_standard_error(exc)


@app.route('/api/forecast/visitors/save', methods=['POST'])
def visitors_save_standard():
    payload, error = _parse_visitors_standard_body()
    if error:
        body, status = error
        return jsonify(body), status

    try:
        forecast_result = _run_visitors_preview(payload)
        save_result = visitors_forecast_service.save_forecast_result(
            forecast_response=forecast_result,
            horizon_label=payload["horizon_label"],
            horizon_count=payload["horizon_count"],
        )
        return jsonify({
            "status": "success",
            "message": "Forecast visitors berhasil disimpan ke database.",
            "request": _visitors_request_meta(payload),
            "save_result": _visitors_save_result_public(save_result),
            "data": _visitors_response_data_public(forecast_result, payload, save_result),
        }), 201
    except Exception as exc:
        return _handle_visitors_standard_error(exc, prefix="Save forecast gagal")


@app.route('/api/forecast/visitors/run', methods=['POST'])
def visitors_run_standard():
    payload, error = _parse_visitors_standard_body()
    if error:
        body, status = error
        return jsonify(body), status

    try:
        forecast_result = _run_visitors_preview(payload)
        save_result = visitors_forecast_service.save_forecast_result(
            forecast_response=forecast_result,
            horizon_label=payload["horizon_label"],
            horizon_count=payload["horizon_count"],
        )
        return jsonify({
            "status": "success",
            "message": "Forecast visitors berhasil dijalankan dan disimpan.",
            "request": _visitors_request_meta(payload),
            "save_result": _visitors_save_result_public(save_result),
            "data": _visitors_response_data_public(forecast_result, payload, save_result),
        }), 201
    except Exception as exc:
        return _handle_visitors_standard_error(exc, prefix="Run forecast gagal")


def _get_request_json():
    return request.get_json(silent=True) or {}


def _get_store_id(payload):
    return payload.get("store_id") or payload.get("m_store_id")


def _parse_start_date(payload):
    start_date_str = payload.get("start_date")
    return date.fromisoformat(start_date_str) if start_date_str else None


def _parse_horizon_label(payload):
    horizon_label = str(payload.get("horizon_label", "daily")).strip().lower()
    allowed = {"daily", "weekly", "monthly"}
    if horizon_label not in allowed:
        raise ValueError("horizon_label harus salah satu dari: daily, weekly, monthly")
    return horizon_label


def _parse_horizon_count(payload, horizon_label):
    default_by_label = {"daily": 30, "weekly": 4, "monthly": 3}
    legacy_key = {"daily": "forecast_days", "weekly": "forecast_weeks", "monthly": "forecast_months"}[horizon_label]
    raw_value = payload.get("horizon_count", payload.get("periods", payload.get(legacy_key, default_by_label[horizon_label])))
    try:
        horizon_count = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError("horizon_count harus berupa angka")
    if horizon_count < 1:
        raise ValueError("horizon_count minimal 1")
    return horizon_count


# ============================================
# ROUTE MODUL SALES (STANDARD LIKE VISITORS)
# ============================================
VALID_FORECAST_HORIZONS = {"daily", "weekly", "monthly"}


def _parse_sales_standard_body():
    req = request.get_json(silent=True) or {}
    store_id = req.get("store_id") or req.get("m_store_id")
    if not store_id:
        return None, ({"detail": "store_id wajib diisi"}, 400)

    horizon_label = req.get("horizon_label")
    if horizon_label not in VALID_FORECAST_HORIZONS:
        return None, ({"detail": "horizon_label harus daily, weekly, atau monthly"}, 400)

    try:
        horizon_count = int(req.get("horizon_count"))
    except (TypeError, ValueError):
        return None, ({"detail": "horizon_count wajib berupa angka"}, 400)
    if horizon_count <= 0:
        return None, ({"detail": "horizon_count harus lebih besar dari 0"}, 400)

    start_date = None
    start_date_str = req.get("start_date")
    if start_date_str:
        try:
            start_date = date.fromisoformat(str(start_date_str)[:10])
        except ValueError:
            return None, ({"detail": "start_date harus format YYYY-MM-DD"}, 400)

    return {
        "store_id": str(store_id),
        "horizon_label": str(horizon_label),
        "horizon_count": horizon_count,
        "start_date": start_date,
    }, None


def _parse_inventory_standard_body():
    req = request.get_json(silent=True) or {}
    store_id = req.get("store_id") or req.get("m_store_id")
    ingredient_id = req.get("ingredient_id") or req.get("m_food_ingredient_id")
    if not store_id or not ingredient_id:
        return None, ({"detail": "store_id dan ingredient_id wajib diisi"}, 400)

    horizon_label = req.get("horizon_label")
    if horizon_label not in VALID_FORECAST_HORIZONS:
        return None, ({"detail": "horizon_label harus daily, weekly, atau monthly"}, 400)

    try:
        horizon_count = int(req.get("horizon_count"))
    except (TypeError, ValueError):
        return None, ({"detail": "horizon_count wajib berupa angka"}, 400)
    if horizon_count <= 0:
        return None, ({"detail": "horizon_count harus lebih besar dari 0"}, 400)

    start_date = None
    start_date_str = req.get("start_date")
    if start_date_str:
        try:
            start_date = date.fromisoformat(str(start_date_str)[:10])
        except ValueError:
            return None, ({"detail": "start_date harus format YYYY-MM-DD"}, 400)

    return {
        "store_id": str(store_id),
        "ingredient_id": str(ingredient_id),
        "horizon_label": str(horizon_label),
        "horizon_count": horizon_count,
        "start_date": start_date,
    }, None


def _forecast_request_meta(payload):
    result = {
        "store_id": payload["store_id"],
        "horizon_label": payload["horizon_label"],
        "horizon_count": payload["horizon_count"],
        "start_date": _date_or_none(payload.get("start_date")),
        "start_date_mode": "manual" if payload.get("start_date") else "auto",
    }
    if payload.get("ingredient_id"):
        result["ingredient_id"] = payload["ingredient_id"]
    return result


def _clean_sales_forecast_item(item, horizon_label):
    if horizon_label == "daily":
        cleaned = {
            "date": item.get("date"),
            "predicted_omzet": item.get("predicted_omzet"),
            "lower_bound": item.get("lower_bound"),
            "upper_bound": item.get("upper_bound"),
            "day_of_week": item.get("day_of_week"),
            "is_weekend": item.get("is_weekend"),
        }
    else:
        cleaned = {
            "period_start": item.get("period_start"),
            "period_end": item.get("period_end"),
            "predicted_omzet": item.get("predicted_omzet"),
            "lower_bound": item.get("lower_bound"),
            "upper_bound": item.get("upper_bound"),
        }
        if horizon_label == "weekly" and item.get("week_of_year") is not None:
            cleaned["week_of_year"] = item.get("week_of_year")
        if horizon_label == "monthly" and item.get("month") is not None:
            cleaned["month"] = item.get("month")
    return {key: value for key, value in cleaned.items() if value is not None}


def _sales_model_metadata_public(raw_metadata, horizon_label, save_result=None):
    raw_metadata = raw_metadata or {}
    model_metrics = raw_metadata.get("metrics") or {}
    save_metrics = (save_result or {}).get("metrics") or {}
    metadata = {
        "trained_at": raw_metadata.get("trained_at"),
        "training_data_points": raw_metadata.get("training_data_points"),
        "metric_horizon": raw_metadata.get("metric_horizon") or horizon_label,
        "horizon_method": raw_metadata.get("horizon_method"),
        "cv_mae": raw_metadata.get("cv_mae"),
        "cv_rmse": raw_metadata.get("cv_rmse"),
        "error_ratio": model_metrics.get(f"{horizon_label}_error_ratio"),
        "wape": model_metrics.get(f"{horizon_label}_wape"),
        "error_percentage": model_metrics.get(f"{horizon_label}_error_percentage") or model_metrics.get(f"{horizon_label}_mae_percentage"),
        "bias": model_metrics.get(f"{horizon_label}_bias"),
        "mean_error": model_metrics.get(f"{horizon_label}_mean_error"),
        "bias_percentage": model_metrics.get(f"{horizon_label}_bias_percentage"),
        "interval_coverage": model_metrics.get(f"{horizon_label}_interval_coverage"),
        "avg_interval_width": model_metrics.get(f"{horizon_label}_avg_interval_width"),
        "relative_interval_width": model_metrics.get(f"{horizon_label}_relative_interval_width"),
        "reliability": model_metrics.get(f"{horizon_label}_reliability"),
        "confidence_level": save_metrics.get("confidence_level"),
        "metrics_version": model_metrics.get("metrics_version"),
        "metric_source": model_metrics.get("metric_source"),
        "feature_importance": raw_metadata.get("feature_importance") or {},
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _standard_save_result_public(save_result):
    if not save_result:
        return None
    return {
        "run_id": save_result.get("run_id"),
        "saved_results": save_result.get("saved_results"),
        "status": "saved",
    }


def _sales_response_data_public(forecast_result, payload, save_result=None):
    raw = _json_model(forecast_result)
    horizon_label = payload["horizon_label"]
    horizon_count = payload["horizon_count"]
    forecasts = [_clean_sales_forecast_item(item, horizon_label) for item in raw.get("forecasts", [])]
    total_predicted = int(sum(float(item.get("predicted_omzet") or 0) for item in forecasts))
    forecast_count = len(forecasts)
    avg_predicted = round(total_predicted / forecast_count, 2) if forecast_count else 0
    forecast_start = raw.get("forecast_start_date")
    forecast_end = raw.get("forecast_end_date")
    horizon_days = _days_between(forecast_start, forecast_end)
    if horizon_days is None and save_result:
        horizon_days = save_result.get("horizon_days")

    return {
        "store_id": raw.get("store_id"),
        "generated_at": raw.get("generated_at"),
        "forecast_start_date": forecast_start,
        "forecast_end_date": forecast_end,
        "horizon": {"label": horizon_label, "count": horizon_count, "days": horizon_days},
        "start_date_source": raw.get("start_date_source"),
        "last_actual_date": raw.get("last_actual_date"),
        "business_cutoff_rule": raw.get("business_cutoff_rule"),
        "summary": {
            "total_predicted_omzet": total_predicted,
            "average_predicted_omzet": avg_predicted,
            "forecast_count": forecast_count,
        },
        "forecasts": forecasts,
        "model_metadata": _sales_model_metadata_public(raw.get("model_metadata"), horizon_label, save_result=save_result),
    }


def _inventory_model_metadata_public(raw_metadata, save_result=None):
    raw_metadata = raw_metadata or {}
    save_metrics = (save_result or {}).get("metrics") or {}
    metadata = {
        "confidence_level": raw_metadata.get("confidence_level") or save_metrics.get("confidence_level"),
        "cv_mae": raw_metadata.get("cv_mae"),
        "cv_rmse": raw_metadata.get("cv_rmse"),
        "error_percentage": raw_metadata.get("error_percentage"),
        "smape": raw_metadata.get("smape"),
        "mape": raw_metadata.get("mape"),
        "r2_score": raw_metadata.get("r2_score"),
        "explained_variance": raw_metadata.get("explained_variance"),
        "bias_ratio": raw_metadata.get("bias_ratio"),
        "data_days": raw_metadata.get("data_days"),
        "cv_initial": raw_metadata.get("cv_initial"),
        "zero_ratio": raw_metadata.get("zero_ratio"),
        "outliers_nullified": raw_metadata.get("outliers_nullified"),
        "stockout_days_nullified": raw_metadata.get("stockout_days_nullified"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _inventory_response_data_public(forecast_result, payload, save_result=None):
    raw = forecast_result or {}
    horizon_label = payload["horizon_label"]
    horizon_count = payload["horizon_count"]
    forecasts = raw.get("forecasts", [])
    forecast_start = raw.get("forecast_start_date")
    forecast_end = raw.get("forecast_end_date")
    horizon_days = _days_between(forecast_start, forecast_end)
    if horizon_days is None:
        horizon_days = (raw.get("horizon") or {}).get("days")
    if horizon_days is None and save_result:
        horizon_days = save_result.get("horizon_days")

    return {
        "store_id": raw.get("store_id"),
        "ingredient_id": raw.get("ingredient_id"),
        "generated_at": raw.get("generated_at"),
        "forecast_start_date": forecast_start,
        "forecast_end_date": forecast_end,
        "horizon": {"label": horizon_label, "count": horizon_count, "days": horizon_days},
        "start_date_source": raw.get("start_date_source"),
        "last_actual_date": raw.get("last_actual_date"),
        "business_cutoff_rule": raw.get("business_cutoff_rule"),
        "summary": raw.get("summary") or {},
        "forecasts": forecasts,
        "model_metadata": _inventory_model_metadata_public(raw.get("model_metadata"), save_result=save_result),
    }


def _run_sales_preview(payload):
    return asyncio.run(sales_forecast_service.forecast_by_horizon(
        store_id=payload["store_id"],
        horizon_label=payload["horizon_label"],
        horizon_count=payload["horizon_count"],
        start_date=payload["start_date"],
    ))


def _run_inventory_preview(payload):
    freq = _map_horizon_to_freq(payload["horizon_label"])
    forecaster = InventoryForecaster(payload["store_id"], payload["ingredient_id"], freq)
    result = forecaster.predict(
        periods=payload["horizon_count"],
        freq=freq,
        start_date=_date_or_none(payload.get("start_date")),
    )
    return forecaster, result


def _handle_standard_error(exc, prefix="Internal server error"):
    if isinstance(exc, FileNotFoundError):
        return jsonify({"detail": str(exc) or "Model belum di-training"}), 404
    if isinstance(exc, ValueError):
        return jsonify({"detail": str(exc)}), 400
    traceback.print_exc()
    return jsonify({"detail": f"{prefix}: {str(exc)}"}), 500


@app.route('/api/forecast/sales/preview', methods=['POST'])
def sales_preview():
    payload, error = _parse_sales_standard_body()
    if error:
        body, status = error
        return jsonify(body), status
    try:
        result = _run_sales_preview(payload)
        return jsonify({
            "status": "success",
            "message": "Forecast sales berhasil dibuat tanpa disimpan.",
            "request": _forecast_request_meta(payload),
            "data": _sales_response_data_public(result, payload),
        }), 200
    except Exception as exc:
        return _handle_standard_error(exc)


@app.route('/api/forecast/sales/save', methods=['POST'])
def sales_save():
    payload, error = _parse_sales_standard_body()
    if error:
        body, status = error
        return jsonify(body), status
    try:
        forecast_result = _run_sales_preview(payload)
        save_result = asyncio.run(sales_forecast_service.save_forecast_result(
            forecast_response=forecast_result,
            horizon_label=payload["horizon_label"],
            horizon_count=payload["horizon_count"],
        ))
        return jsonify({
            "status": "success",
            "message": "Forecast sales berhasil disimpan ke database.",
            "request": _forecast_request_meta(payload),
            "save_result": _standard_save_result_public(save_result),
            "data": _sales_response_data_public(forecast_result, payload, save_result),
        }), 201
    except Exception as exc:
        return _handle_standard_error(exc, prefix="Save forecast gagal")


@app.route('/api/forecast/sales/run', methods=['POST'])
def sales_run():
    payload, error = _parse_sales_standard_body()
    if error:
        body, status = error
        return jsonify(body), status
    try:
        forecast_result = _run_sales_preview(payload)
        save_result = asyncio.run(sales_forecast_service.save_forecast_result(
            forecast_response=forecast_result,
            horizon_label=payload["horizon_label"],
            horizon_count=payload["horizon_count"],
        ))
        return jsonify({
            "status": "success",
            "message": "Forecast sales berhasil dijalankan dan disimpan.",
            "request": _forecast_request_meta(payload),
            "save_result": _standard_save_result_public(save_result),
            "data": _sales_response_data_public(forecast_result, payload, save_result),
        }), 201
    except Exception as exc:
        return _handle_standard_error(exc, prefix="Run forecast gagal")


@app.route('/api/forecast/sales/retrain', methods=['POST'])
def sales_retrain():
    req = request.get_json(silent=True) or {}
    if 'store_id' not in req:
        return jsonify({"detail": "store_id wajib diisi"}), 400
    store_id = req['store_id']
    force = req.get('force', False)
    try:
        result = asyncio.run(sales_forecast_service.retrain(store_id=store_id, force=force))
        return jsonify(_json_model(result)), 200
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Retrain gagal: {str(e)}"}), 500


# ============================================
# ROUTE INVENTORY
# ============================================
@app.route('/api/inventory/train/start', methods=['POST'])
def start_training():
    """Memulai training async dan mengembalikan task_id."""
    task_id = str(uuid.uuid4())
    with threading.Lock():
        training_tasks[task_id] = {
            "status": "STARTING",
            "total": 0,
            "processed": 0,
            "current_pair": None,
            "message": ""
        }
    thread = threading.Thread(target=train_all_inventory_models, args=(task_id,))
    thread.start()
    return jsonify({
        "task_id": task_id,
        "message": "Training dimulai. Pantau progress di /api/inventory/train/status/<task_id>"
    })


@app.route('/api/inventory/train/status/<task_id>', methods=['GET'])
def get_training_status(task_id):
    """Mengembalikan status training berdasarkan task_id."""
    task = training_tasks.get(task_id)
    if not task:
        return jsonify({"detail": "Task tidak ditemukan"}), 404
    return jsonify(task)


@app.route('/api/forecast/inventory/preview', methods=['POST'])
def inventory_preview():
    payload, error = _parse_inventory_standard_body()
    if error:
        body, status = error
        return jsonify(body), status
    try:
        _, result = _run_inventory_preview(payload)
        return jsonify({
            "status": "success",
            "message": "Forecast inventory berhasil dibuat tanpa disimpan.",
            "request": _forecast_request_meta(payload),
            "data": _inventory_response_data_public(result, payload),
        }), 200
    except Exception as exc:
        return _handle_standard_error(exc)


@app.route('/api/forecast/inventory/save', methods=['POST'])
def inventory_save():
    payload, error = _parse_inventory_standard_body()
    if error:
        body, status = error
        return jsonify(body), status
    try:
        forecaster, forecast_result = _run_inventory_preview(payload)
        save_result = forecaster.save_forecast_result(forecast_result)
        return jsonify({
            "status": "success",
            "message": "Forecast inventory berhasil disimpan ke database.",
            "request": _forecast_request_meta(payload),
            "save_result": _standard_save_result_public(save_result),
            "data": _inventory_response_data_public(forecast_result, payload, save_result),
        }), 201
    except Exception as exc:
        return _handle_standard_error(exc, prefix="Save forecast gagal")


@app.route('/api/forecast/inventory/run', methods=['POST'])
def inventory_run():
    payload, error = _parse_inventory_standard_body()
    if error:
        body, status = error
        return jsonify(body), status
    try:
        forecaster, forecast_result = _run_inventory_preview(payload)
        save_result = forecaster.save_forecast_result(forecast_result)
        return jsonify({
            "status": "success",
            "message": "Forecast inventory berhasil dijalankan dan disimpan.",
            "request": _forecast_request_meta(payload),
            "save_result": _standard_save_result_public(save_result),
            "data": _inventory_response_data_public(forecast_result, payload, save_result),
        }), 201
    except Exception as exc:
        return _handle_standard_error(exc, prefix="Run forecast gagal")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)