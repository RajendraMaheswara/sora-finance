from flask import Flask, request, jsonify
from config import Config
from modules.shared.forecast_helpers import (
    add_predicted_value_aliases,
    map_horizon_to_freq as shared_map_horizon_to_freq,
    parse_horizon_count as shared_parse_horizon_count,
    parse_horizon_label as shared_parse_horizon_label,
    parse_standard_body,
    parse_start_date as shared_parse_start_date,
    public_save_result,
    resolve_start_date_from_latest_complete,
    scheduler_run_exists,
    standard_request_meta as shared_standard_request_meta,
    standard_retrain_response,
    to_json_model,
    validate_uuid as shared_validate_uuid,
)
import os
import traceback
import uuid
import threading
import sys
import asyncio
from datetime import datetime, date, timedelta

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
    return shared_map_horizon_to_freq(horizon_label)

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
    if not request.path.startswith("/api/forecast/"):
        return

    expected = str(Config.INTERNAL_SERVICE_KEY or "").strip()
    if not expected:
        # Development mode without service key configured. Backend internal routes
        # still require X-Service-Key when saving to DB.
        return

    provided = (request.headers.get("X-Service-Key") or "").strip()
    auth_header = (request.headers.get("Authorization") or "").strip()
    if not provided and auth_header.startswith("Bearer "):
        provided = auth_header.split(" ", 1)[1].strip()

    if not provided:
        return jsonify({"detail": "Missing internal service key. Use X-Service-Key or Authorization: Bearer <key>."}), 401
    if provided != expected:
        return jsonify({"detail": "Unauthorized internal service key"}), 401


# ============================================
# VISITORS SCHEDULER
# ============================================
# In-memory guard mencegah job ganda dalam proses yang sama.
# Persistent idempotency dicek ke DB melalui scheduler_run_exists().
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
                if scheduler_run_exists(
                    forecast_type="visitors",
                    store_id=str(job.get("store_id")),
                    horizon_label=str(job.get("horizon_label")),
                    predict_start_date=job.get("start_date"),
                ):
                    with _VISITORS_SCHEDULER_LOCK:
                        _VISITORS_SCHEDULER_RUN_KEYS.add(key)
                    continue
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

# ============================================
# SALES SCHEDULER
# ============================================
_SALES_SCHEDULER_RUN_KEYS = set()
_SALES_SCHEDULER_RUNNING_KEYS = set()
_SALES_SCHEDULER_LOCK = threading.Lock()


def _sales_scheduler_key(job):
    start_date = job.get("start_date")
    if isinstance(start_date, date):
        start_value = start_date.isoformat()
    else:
        start_value = str(start_date)
    return (str(job.get("store_id")), str(job.get("horizon_label")), start_value)


async def _run_sales_scheduler_once_async():
    """Cek semua store dan jalankan sales forecast yang sudah due."""
    store_ids = await golang_client.fetch_store_ids()
    if not store_ids:
        logger.warning("Sales scheduler: tidak ada store dari backend internal /stores")
        return []

    results = []
    for store_id in store_ids:
        try:
            operational_hours = await golang_client.fetch_store_operational_hours(store_id)
            jobs = sales_forecast_service.build_scheduler_jobs_for_store(
                store_id=store_id,
                operational_hours=operational_hours,
            )

            due_jobs = []
            for job in jobs:
                key = _sales_scheduler_key(job)
                if scheduler_run_exists(
                    forecast_type="sales",
                    store_id=str(job.get("store_id")),
                    horizon_label=str(job.get("horizon_label")),
                    predict_start_date=job.get("start_date"),
                ):
                    with _SALES_SCHEDULER_LOCK:
                        _SALES_SCHEDULER_RUN_KEYS.add(key)
                    continue
                with _SALES_SCHEDULER_LOCK:
                    if key in _SALES_SCHEDULER_RUN_KEYS or key in _SALES_SCHEDULER_RUNNING_KEYS:
                        continue
                    _SALES_SCHEDULER_RUNNING_KEYS.add(key)
                due_jobs.append((key, job))

            if not due_jobs:
                continue

            if Config.SCHEDULER_RETRAIN:
                logger.info("Sales scheduler: retrain store=%s sebelum auto forecast", store_id)
                await sales_forecast_service.retrain(store_id=store_id, force=True)

            for key, job in due_jobs:
                try:
                    logger.info(
                        "Sales scheduler: run store=%s horizon=%s start_date=%s",
                        store_id,
                        job["horizon_label"],
                        job["start_date"],
                    )
                    
                    if job["horizon_label"] == "daily":
                        forecast_result = await sales_forecast_service.forecast(
                            store_id=store_id,
                            forecast_days=job.get("horizon_count", 30),
                            start_date=job["start_date"],
                        )
                    elif job["horizon_label"] == "weekly":
                        forecast_result = await sales_forecast_service.forecast_weekly(
                            store_id=store_id,
                            forecast_weeks=job.get("horizon_count", 12),
                            start_date=job["start_date"],
                        )
                    else:
                        forecast_result = await sales_forecast_service.forecast_monthly(
                            store_id=store_id,
                            forecast_months=job.get("horizon_count", 12),
                            start_date=job["start_date"],
                        )

                    if hasattr(forecast_result, "start_date_source"):
                        forecast_result.start_date_source = job.get("start_date_source")
                    if hasattr(forecast_result, "business_cutoff_rule"):
                        forecast_result.business_cutoff_rule = job.get("business_cutoff_rule")
                    if hasattr(forecast_result, "last_actual_date"):
                        forecast_result.last_actual_date = job.get("latest_complete_day")

                    forecast_dict = forecast_result.model_dump(mode="json") if hasattr(forecast_result, "model_dump") else forecast_result.dict()
                    forecast_dict["request_meta"] = {
                        "module": "sales",
                        "horizon_label": job.get("horizon_label"),
                        "horizon_count": job.get("horizon_count", 1),
                        "mode": "scheduler",
                        "saved_to_database": True,
                    }
                    save_result = await sales_forecast_service.save_forecast_to_db(
                        store_id=store_id,
                        forecast_response=forecast_dict,
                    )
                    
                    with _SALES_SCHEDULER_LOCK:
                        if save_result.get("status") == "saved":
                            _SALES_SCHEDULER_RUN_KEYS.add(key)
                    results.append({
                        "store_id": store_id,
                        "horizon_label": job["horizon_label"],
                        "start_date": job["start_date"].isoformat() if isinstance(job["start_date"], date) else job["start_date"],
                        "run_id": save_result.get("run_id"),
                        "saved_results": save_result.get("saved_results"),
                        "status": save_result.get("status"),
                        "message": save_result.get("message"),
                    })
                except Exception:
                    traceback.print_exc()
                finally:
                    with _SALES_SCHEDULER_LOCK:
                        _SALES_SCHEDULER_RUNNING_KEYS.discard(key)
        except Exception:
            traceback.print_exc()

    if results:
        logger.info("Sales scheduler selesai: %s job tersimpan", len(results))
    return results


def scheduled_sales_forecast_check():
    try:
        asyncio.run(_run_sales_scheduler_once_async())
    except Exception:
        traceback.print_exc()


# ============================================
# INVENTORY SCHEDULER
# ============================================
_INVENTORY_SCHEDULER_RUN_KEYS = set()
_INVENTORY_SCHEDULER_RUNNING_KEYS = set()
_INVENTORY_SCHEDULER_LOCK = threading.Lock()

def _inventory_scheduler_key(job, ingredient_id):
    start_date = job.get("start_date")
    start_value = start_date.isoformat() if isinstance(start_date, date) else str(start_date)
    return (str(job.get("store_id")), str(ingredient_id), str(job.get("horizon_label")), start_value)

async def _run_inventory_scheduler_once_async():
    """Cek semua store dan jalankan inventory forecast yang sudah due."""
    store_ids = await golang_client.fetch_store_ids()
    if not store_ids:
        logger.warning("Inventory scheduler: tidak ada store dari backend internal /stores")
        return []

    results = []
    for store_id in store_ids:
        try:
            operational_hours = await golang_client.fetch_store_operational_hours(store_id)
            jobs = visitors_forecast_service.build_scheduler_jobs_for_store(
                store_id=store_id,
                operational_hours=operational_hours,
            )
            
            if not jobs:
                continue

            # Ambil semua ingredient id dari store tersebut
            ingredients_resp = await golang_client._get("food-ingredients", params={"store_id": store_id})
            ingredients = golang_client._extract_items(ingredients_resp)
            if not ingredients:
                continue
                
            due_jobs = []
            for job in jobs:
                for ingredient in ingredients:
                    ing_id = str(ingredient.get("id", ""))
                    if not ing_id:
                        continue
                    key = _inventory_scheduler_key(job, ing_id)
                    if scheduler_run_exists(
                        forecast_type="inventory",
                        store_id=str(job.get("store_id")),
                        horizon_label=str(job.get("horizon_label")),
                        predict_start_date=job.get("start_date"),
                        item_id=ing_id,
                    ):
                        with _INVENTORY_SCHEDULER_LOCK:
                            _INVENTORY_SCHEDULER_RUN_KEYS.add(key)
                        continue
                    with _INVENTORY_SCHEDULER_LOCK:
                        if key in _INVENTORY_SCHEDULER_RUN_KEYS or key in _INVENTORY_SCHEDULER_RUNNING_KEYS:
                            continue
                        _INVENTORY_SCHEDULER_RUNNING_KEYS.add(key)
                    due_jobs.append((key, job, ing_id))
            
            if not due_jobs:
                continue
                
            for key, job, ing_id in due_jobs:
                try:
                    logger.info(
                        "Inventory scheduler: run store=%s ingredient=%s horizon=%s start_date=%s",
                        store_id, ing_id, job["horizon_label"], job["start_date"]
                    )
                    freq = _map_horizon_to_freq(job["horizon_label"])
                    periods = int(job.get("horizon_count") or 1)
                    if periods < 1:
                        periods = 1
                    
                    forecaster = InventoryForecaster(store_id, ing_id, freq)
                    save_result = forecaster.save_all_forecasts(
                        periods=periods,
                        freq=freq,
                        start_date=job["start_date"],
                        start_date_source=job.get("start_date_source"),
                        business_cutoff_rule=job.get("business_cutoff_rule"),
                        last_actual_date=job.get("latest_complete_day"),
                    )
                    
                    with _INVENTORY_SCHEDULER_LOCK:
                        if save_result.get("status") == "saved":
                            _INVENTORY_SCHEDULER_RUN_KEYS.add(key)
                    
                    results.append({
                        "store_id": store_id,
                        "ingredient_id": ing_id,
                        "horizon_label": job["horizon_label"],
                        "run_id": save_result.get("run_id"),
                        "saved_results": save_result.get("saved_results"),
                        "status": save_result.get("status"),
                    })
                except Exception:
                    traceback.print_exc()
                finally:
                    with _INVENTORY_SCHEDULER_LOCK:
                        _INVENTORY_SCHEDULER_RUNNING_KEYS.discard(key)
        except Exception:
            traceback.print_exc()
            
    if results:
        logger.info("Inventory scheduler selesai: %s job tersimpan", len(results))
    return results

def scheduled_inventory_forecast_check():
    try:
        asyncio.run(_run_inventory_scheduler_once_async())
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
    scheduler.add_job(
        func=scheduled_sales_forecast_check,
        trigger="interval",
        minutes=Config.FORECAST_SCHEDULER_CHECK_INTERVAL_MINUTES,
        id="sales_auto_forecast_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        func=scheduled_inventory_forecast_check,
        trigger="interval",
        minutes=Config.FORECAST_SCHEDULER_CHECK_INTERVAL_MINUTES,
        id="inventory_auto_forecast_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
    logger.info(
        "Forecast scheduler enabled: interval=%s minutes, after_close=%s minutes, 24h_cutoff=%s minutes, retrain=%s",
        Config.FORECAST_SCHEDULER_CHECK_INTERVAL_MINUTES,
        Config.FORECAST_AFTER_CLOSE_SCHEDULER_MINUTES,
        Config.FORECAST_24H_RUN_SCHEDULER_MINUTES,
        Config.SCHEDULER_RETRAIN,
    )
else:
    logger.info("Forecast scheduler disabled because FORECAST_MODE=%s", Config.FORECAST_MODE)

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
        store_id = _validate_uuid(store_id, "store_id")
        result = asyncio.run(visitors_forecast_service.retrain(
            store_id=store_id,
            force=force
        ))
        return jsonify(standard_retrain_response(
            "visitors",
            result,
            {"module": "visitors", "store_id": store_id, "force": bool(force)},
        )), 200
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Retrain gagal: {str(e)}"}), 500

VALID_VISITORS_HORIZONS = {"daily", "weekly", "monthly"}


def _parse_visitors_standard_body():
    try:
        payload = parse_standard_body(_get_request_json(), module="visitors")
        return payload, None
    except ValueError as exc:
        return None, ({"detail": str(exc)}, 400)


def _json_model(result):
    return to_json_model(result)


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
    return public_save_result(save_result)


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
            "message": "Forecast visitors berhasil dijalankan dan disimpan ke database.",
            "request": _visitors_request_meta(payload),
            "save_result": _visitors_save_result_public(save_result),
            "data": _visitors_response_data_public(forecast_result, payload, save_result),
        }), 201
    except Exception as exc:
        return _handle_visitors_standard_error(exc, prefix="Save forecast gagal")


def _get_request_json():
    return request.get_json(silent=True) or {}


def _get_store_id(payload):
    return payload.get("store_id") or payload.get("m_store_id")


def _parse_start_date(payload):
    return shared_parse_start_date(payload)


def _parse_horizon_label(payload):
    return shared_parse_horizon_label(payload)


def _parse_horizon_count(payload, horizon_label):
    return shared_parse_horizon_count(payload, horizon_label)


def _validate_uuid(value, field_name):
    return shared_validate_uuid(value, field_name)


def _standard_request_meta(module, payload, extra=None):
    return shared_standard_request_meta(module, payload, extra)


async def _resolve_inventory_start_date_meta(store_id, horizon_label, requested_start_date):
    operational_hours = await golang_client.fetch_store_operational_hours(store_id)
    latest_complete_day = visitors_forecast_service._latest_complete_day_by_operational_hours(operational_hours)
    return resolve_start_date_from_latest_complete(
        latest_complete_day=latest_complete_day,
        horizon_label=horizon_label,
        requested_start_date=requested_start_date,
    )


def _parse_inventory_standard_body(payload):
    return parse_standard_body(payload, module="inventory", require_ingredient=True)


def _standard_inventory_response(result, payload, message, save_result=None):
    body = {
        "status": "success",
        "message": message,
        "request": _standard_request_meta(
            "inventory",
            payload,
            {
                "ingredient_id": payload.get("ingredient_id"),
                "start_date_mode": payload.get("start_date_mode"),
            },
        ),
        "data": result,
    }
    if save_result is not None:
        body["save_result"] = save_result
    return body


# ============================================
# ROUTE MODUL SALES (NEW STANDARD ROUTES)
# ============================================

def _parse_sales_standard_body(payload):
    return parse_standard_body(payload, module="sales")


async def _run_sales_forecast_from_payload(payload):
    parsed = _parse_sales_standard_body(payload)
    store_id = parsed["store_id"]
    horizon_label = parsed["horizon_label"]
    horizon_count = parsed["horizon_count"]
    start_date_val = parsed.get("start_date")

    if horizon_label == "daily":
        result = await sales_forecast_service.forecast(
            store_id=store_id,
            forecast_days=horizon_count,
            start_date=start_date_val,
        )
    elif horizon_label == "weekly":
        result = await sales_forecast_service.forecast_weekly(
            store_id=store_id,
            forecast_weeks=horizon_count,
            start_date=start_date_val,
        )
    else:
        result = await sales_forecast_service.forecast_monthly(
            store_id=store_id,
            forecast_months=horizon_count,
            start_date=start_date_val,
        )

    response = _json_model(result)
    response = add_predicted_value_aliases(response, predicted_key="predicted_omzet")
    response["request_meta"] = {
        "module": "sales",
        "store_id": store_id,
        "horizon_label": horizon_label,
        "horizon_count": horizon_count,
        "mode": "preview",
        "saved_to_database": False,
    }
    return response, parsed


def _standard_sales_response(result, payload, message, save_result=None):
    body = {
        "status": "success",
        "message": message,
        "request": _standard_request_meta("sales", payload),
        "data": result,
    }
    if save_result is not None:
        body["save_result"] = public_save_result(save_result)
    return body

@app.route('/api/forecast/sales/preview', methods=['POST'])
def sales_preview():
    try:
        result, payload = asyncio.run(_run_sales_forecast_from_payload(_get_request_json()))
        return jsonify(_standard_sales_response(
            result,
            payload,
            f"Preview forecast sales {payload['horizon_label']} berhasil.",
        )), 200
    except FileNotFoundError as e:
        return jsonify({"detail": str(e)}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500

@app.route('/api/forecast/sales/save', methods=['POST'])
def sales_save():
    """Generate + simpan forecast sales ke database."""
    try:
        result, payload = asyncio.run(_run_sales_forecast_from_payload(_get_request_json()))
        result["request_meta"]["mode"] = "save"
        result["request_meta"]["saved_to_database"] = True

        save_result = asyncio.run(sales_forecast_service.save_forecast_to_db(payload["store_id"], result))
        if save_result.get("status") != "saved":
            return jsonify({"detail": save_result.get("message", "Gagal menyimpan forecast sales"), "save_result": public_save_result(save_result)}), 500

        return jsonify(_standard_sales_response(
            result,
            payload,
            f"Forecast sales {payload['horizon_label']} berhasil dijalankan dan disimpan ke database.",
            save_result=save_result,
        )), 201
    except FileNotFoundError as e:
        return jsonify({"detail": str(e)}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500

@app.route('/api/forecast/sales/retrain', methods=['POST'])
def sales_retrain():
    req = request.get_json()
    if not req or 'store_id' not in req:
        return jsonify({"detail": "store_id wajib diisi"}), 400
    
    store_id = req['store_id']
    force = req.get('force', False)

    try:
        store_id = _validate_uuid(store_id, "store_id")
        result = asyncio.run(sales_forecast_service.retrain(store_id=store_id, force=force))
        return jsonify(standard_retrain_response(
            "sales",
            result,
            {"module": "sales", "store_id": store_id, "force": bool(force)},
        )), 200
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
        return jsonify({"error": "Task tidak ditemukan"}), 404
    return jsonify(task)

@app.route('/api/forecast/inventory/retrain', methods=['POST'])
def inventory_retrain():
    req = request.get_json(silent=True) or {}
    if 'store_id' not in req and 'm_store_id' not in req:
        return jsonify({"detail": "store_id wajib diisi"}), 400

    try:
        from modules.inventory.trainer import retrain_inventory_store

        store_id = _validate_uuid(_get_store_id(req), "store_id")
        force = req.get('force', False)
        result = retrain_inventory_store(store_id=store_id, force=bool(force))
        return jsonify(standard_retrain_response(
            "inventory",
            result,
            {"module": "inventory", "store_id": store_id, "force": bool(force)},
        )), 200
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Retrain gagal: {str(e)}"}), 500

@app.route('/api/forecast/inventory/preview', methods=['POST'])
def inventory_preview():
    """Preview forecast inventory tanpa menyimpan ke database."""
    try:
        raw_payload = _get_request_json()
        payload = _parse_inventory_standard_body(raw_payload)
        freq = _map_horizon_to_freq(payload["horizon_label"])
        start_meta = asyncio.run(_resolve_inventory_start_date_meta(
            payload["store_id"],
            payload["horizon_label"],
            payload.get("start_date"),
        ))

        forecaster = InventoryForecaster(payload["store_id"], payload["ingredient_id"], freq)
        result = forecaster.predict(
            periods=payload["horizon_count"],
            freq=freq,
            start_date=start_meta["start_date"],
            start_date_source=start_meta.get("start_date_source"),
            business_cutoff_rule=start_meta.get("business_cutoff_rule"),
        )
        if start_meta.get("latest_complete_day"):
            result["last_actual_date"] = start_meta["latest_complete_day"].isoformat() if hasattr(start_meta["latest_complete_day"], "isoformat") else str(start_meta["latest_complete_day"])

        response_payload = dict(payload)
        response_payload["start_date"] = start_meta["start_date"]
        response_payload["start_date_mode"] = start_meta.get("start_date_mode", "auto")
        return jsonify(_standard_inventory_response(
            result,
            response_payload,
            f"Preview forecast inventory {payload['horizon_label']} berhasil.",
        )), 200
    except FileNotFoundError:
        return jsonify({"detail": "Model inventory belum di-training"}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500


@app.route('/api/forecast/inventory/save', methods=['POST'])
def inventory_save():
    """Generate + simpan forecast inventory ke database."""
    try:
        raw_payload = _get_request_json()
        payload = _parse_inventory_standard_body(raw_payload)
        freq = _map_horizon_to_freq(payload["horizon_label"])
        start_meta = asyncio.run(_resolve_inventory_start_date_meta(
            payload["store_id"],
            payload["horizon_label"],
            payload.get("start_date"),
        ))

        forecaster = InventoryForecaster(payload["store_id"], payload["ingredient_id"], freq)
        result = forecaster.predict(
            periods=payload["horizon_count"],
            freq=freq,
            start_date=start_meta["start_date"],
            start_date_source=start_meta.get("start_date_source"),
            business_cutoff_rule=start_meta.get("business_cutoff_rule"),
        )
        if start_meta.get("latest_complete_day"):
            result["last_actual_date"] = start_meta["latest_complete_day"].isoformat() if hasattr(start_meta["latest_complete_day"], "isoformat") else str(start_meta["latest_complete_day"])
        save_result = forecaster.save_all_forecasts(
            periods=payload["horizon_count"],
            freq=freq,
            start_date=start_meta["start_date"],
            forecast_result=result,
            start_date_source=start_meta.get("start_date_source"),
            business_cutoff_rule=start_meta.get("business_cutoff_rule"),
            last_actual_date=start_meta.get("latest_complete_day"),
        )

        if save_result.get("status") != "saved":
            return jsonify({"detail": save_result.get("message", "Gagal menyimpan forecast inventory"), "save_result": save_result}), 500

        response_payload = dict(payload)
        response_payload["start_date"] = start_meta["start_date"]
        response_payload["start_date_mode"] = start_meta.get("start_date_mode", "auto")
        return jsonify(_standard_inventory_response(
            result,
            response_payload,
            f"Forecast inventory {payload['horizon_label']} berhasil disimpan ke database.",
            save_result=public_save_result(save_result),
        )), 201
    except FileNotFoundError:
        return jsonify({"detail": "Model inventory belum di-training"}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)