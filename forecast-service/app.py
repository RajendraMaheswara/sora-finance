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
import json
import requests
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
from modules.inventory.forecaster import InventoryForecaster, InventoryModelNotAvailableError
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
    parsed = parse_standard_body(payload, module="inventory", require_ingredient=False)
    ingredient_id = payload.get("ingredient_id") or payload.get("m_food_ingredient_id")
    if ingredient_id not in (None, ""):
        parsed["ingredient_id"] = _validate_uuid(ingredient_id, "ingredient_id")
    return parsed


def _standard_inventory_response(result, payload, message, save_result=None, status="success"):
    ingredient_id = payload.get("ingredient_id")
    body = {
        "status": status,
        "message": message,
        "request": _standard_request_meta(
            "inventory",
            payload,
            {
                "ingredient_id": ingredient_id,
                "ingredient_mode": "single" if ingredient_id else "all_store_ingredients",
                "start_date_mode": payload.get("start_date_mode"),
            },
        ),
        "data": result,
    }
    if isinstance(result, dict):
        if result.get("warnings"):
            body["warnings"] = result.get("warnings")
        if result.get("errors"):
            body["errors"] = result.get("errors")
    if save_result is not None:
        body["save_result"] = save_result
    return body



def _inventory_ingredient_id_from_item(item):
    value = (
        item.get("id")
        or item.get("ingredient_id")
        or item.get("m_food_ingredient_id")
        or item.get("food_ingredient_id")
        or item.get("mFoodIngredientId")
    )
    return str(value) if value else None


def _inventory_item_belongs_to_store(item, store_id):
    value = item.get("m_store_id") or item.get("store_id") or item.get("storeId") or item.get("mStoreId")
    # Be defensive: beberapa internal endpoint sudah melakukan scoping by store dan
    # response lama tidak selalu membawa store_id. Dalam kasus itu, jangan drop item.
    return value in (None, "") or str(value) == str(store_id)


async def _fetch_inventory_ingredient_ids(store_id):
    ingredients_resp = await golang_client._get("food-ingredients", params={"store_id": store_id})
    ingredients = golang_client._extract_items(ingredients_resp)
    ingredient_ids = []
    seen = set()
    for item in ingredients:
        if not _inventory_item_belongs_to_store(item, store_id):
            continue
        ingredient_id = _inventory_ingredient_id_from_item(item)
        if not ingredient_id:
            continue
        ingredient_id = _validate_uuid(ingredient_id, "ingredient_id")
        if ingredient_id not in seen:
            ingredient_ids.append(ingredient_id)
            seen.add(ingredient_id)
    return ingredient_ids


def _inventory_forecast_bounds(result):
    forecasts = result.get("forecasts") or []
    if not forecasts:
        return None, None
    first = forecasts[0]
    last = forecasts[-1]
    start_value = first.get("date") or first.get("period_start") or result.get("forecast_start_date")
    end_value = last.get("date") or last.get("period_end") or result.get("forecast_end_date")
    return start_value, end_value


def _inventory_result_rows_for_backend(result, ingredient_id):
    horizon_label = (result.get("horizon") or {}).get("label", "daily")
    date_key = "date" if horizon_label == "daily" else "period_start"
    model_meta = result.get("model_metadata") or {}
    confidence_level = int(model_meta.get("confidence_level") or 0)
    rows = []
    for item in result.get("forecasts") or []:
        target_date = item.get(date_key) or item.get("date") or item.get("period_start")
        if not target_date:
            raise ValueError(f"target_date kosong untuk ingredient {ingredient_id}")
        rows.append({
            "target_date": target_date,
            "predicted_value": float(item.get("predicted_usage", item.get("predicted_value", 0.0))),
            "lower_bound": item.get("lower_bound"),
            "upper_bound": item.get("upper_bound"),
            "confidence_level": confidence_level,
            "item_id": ingredient_id,
            "item_type": "ingredient",
        })
    return rows


def _inventory_model_training_info(forecaster):
    if forecaster.model is not None and hasattr(forecaster.model, "history") and not forecaster.model.history.empty:
        hist = forecaster.model.history
        return {
            "train_start_date": hist["ds"].min().strftime("%Y-%m-%d"),
            "train_end_date": hist["ds"].max().strftime("%Y-%m-%d"),
            "training_rows": int(len(hist)),
        }
    today = datetime.now().date().isoformat()
    return {"train_start_date": today, "train_end_date": today, "training_rows": 0}


def _inventory_issue(ingredient_id, *, status, reason_code, message, detail=None):
    issue = {
        "ingredient_id": ingredient_id,
        "status": status,
        "reason_code": reason_code,
        "message": message,
        # Backward-compatible alias for older callers that read `error`.
        "error": message,
    }
    if detail:
        issue["detail"] = detail
    return issue


def _inventory_no_model_issue(ingredient_id, exc=None):
    reason_code = getattr(exc, "reason_code", None) or "no_training_history_or_model"
    return _inventory_issue(
        ingredient_id,
        status="skipped",
        reason_code=reason_code,
        message="Belum ada histori stok; model forecast belum tersedia.",
    )


def _inventory_missing_store_model_issue(ingredient_id, exc=None):
    return _inventory_issue(
        ingredient_id,
        status="skipped",
        reason_code="store_model_not_trained",
        message="Model inventory toko belum di-training untuk horizon ini.",
        detail=str(exc) if exc else None,
    )


def _inventory_failed_issue(ingredient_id, exc):
    return _inventory_issue(
        ingredient_id,
        status="failed",
        reason_code="forecast_failed",
        message=str(exc),
    )


def _split_inventory_issues(issues):
    issues = issues or []
    skipped = [item for item in issues if item.get("status") == "skipped"]
    failed = [item for item in issues if item.get("status") != "skipped"]
    return skipped, failed


def _inventory_issue_summary(issues):
    skipped, failed = _split_inventory_issues(issues)
    return {
        "skipped_ingredient_count": len(skipped),
        "failed_ingredient_count": len(failed),
        "unsuccessful_ingredient_count": len(issues or []),
        "skipped_ingredients": skipped,
        "failed_ingredients": failed,
        "warnings": skipped,
        # Keep `errors` semantically strict: only real runtime failures, not no-history skips.
        "errors": failed,
    }


def _run_inventory_single_forecast(store_id, ingredient_id, payload, freq, start_meta):
    forecaster = InventoryForecaster(store_id, ingredient_id, freq)
    result = forecaster.predict(
        periods=payload["horizon_count"],
        freq=freq,
        start_date=start_meta["start_date"],
        start_date_source=start_meta.get("start_date_source"),
        business_cutoff_rule=start_meta.get("business_cutoff_rule"),
    )
    if start_meta.get("latest_complete_day"):
        result["last_actual_date"] = start_meta["latest_complete_day"].isoformat() if hasattr(start_meta["latest_complete_day"], "isoformat") else str(start_meta["latest_complete_day"])
    training_info = _inventory_model_training_info(forecaster)
    return {"ingredient_id": ingredient_id, "result": result, "forecaster": forecaster, "training_info": training_info}


async def _run_inventory_forecasts_from_payload(payload, freq, start_meta):
    single_mode = bool(payload.get("ingredient_id"))
    if single_mode:
        ingredient_ids = [payload["ingredient_id"]]
    else:
        ingredient_ids = await _fetch_inventory_ingredient_ids(payload["store_id"])
        if not ingredient_ids:
            raise ValueError("Tidak ada ingredient untuk store_id tersebut")

    forecasts = []
    errors = []
    for ingredient_id in ingredient_ids:
        try:
            forecasts.append(_run_inventory_single_forecast(
                payload["store_id"],
                ingredient_id,
                payload,
                freq,
                start_meta,
            ))
        except InventoryModelNotAvailableError as exc:
            if single_mode:
                raise
            errors.append(_inventory_no_model_issue(ingredient_id, exc))
        except FileNotFoundError as exc:
            if single_mode:
                raise
            errors.append(_inventory_missing_store_model_issue(ingredient_id, exc))
        except Exception as exc:
            if single_mode:
                raise
            errors.append(_inventory_failed_issue(ingredient_id, exc))

    if not forecasts:
        skipped, failed = _split_inventory_issues(errors)
        if errors and len(skipped) == len(errors):
            raise FileNotFoundError(
                "Tidak ada ingredient yang bisa diprediksi karena belum ada histori stok/model forecast."
            )
        raise ValueError("Forecast inventory gagal untuk semua ingredient yang diminta")

    return forecasts, errors, ingredient_ids


def _aggregate_inventory_response(store_id, payload, forecast_items, errors=None):
    errors = errors or []
    issue_summary = _inventory_issue_summary(errors)
    if len(forecast_items) == 1 and payload.get("ingredient_id"):
        result = forecast_items[0]["result"]
        if errors:
            result = dict(result)
            result.update(issue_summary)
        return result

    ingredient_results = []
    total_predicted_usage = 0.0
    total_forecast_count = 0
    starts = []
    ends = []
    confidence_levels = []
    per_ingredient_summary = []

    for item in forecast_items:
        ingredient_id = item["ingredient_id"]
        result = item["result"]
        summary = result.get("summary") or {}
        model_meta = result.get("model_metadata") or {}
        start_value, end_value = _inventory_forecast_bounds(result)
        if start_value:
            starts.append(str(start_value))
        if end_value:
            ends.append(str(end_value))
        total_value = float(summary.get("total_predicted_usage") or summary.get("total_predicted_value") or 0.0)
        forecast_count = int(summary.get("forecast_count") or len(result.get("forecasts") or []))
        total_predicted_usage += total_value
        total_forecast_count += forecast_count
        if model_meta.get("confidence_level") is not None:
            confidence_levels.append(float(model_meta.get("confidence_level") or 0))
        per_ingredient_summary.append({
            "ingredient_id": ingredient_id,
            "forecast_count": forecast_count,
            "total_predicted_usage": round(total_value, 2),
            "average_predicted_usage": summary.get("average_predicted_usage"),
            "confidence_level": model_meta.get("confidence_level"),
        })
        ingredient_results.append({
            "ingredient_id": ingredient_id,
            "forecast_start_date": result.get("forecast_start_date"),
            "forecast_end_date": result.get("forecast_end_date"),
            "last_actual_date": result.get("last_actual_date"),
            "model_metadata": model_meta,
            "summary": summary,
            "forecasts": result.get("forecasts") or [],
        })

    first_result = forecast_items[0]["result"]
    avg_confidence = round(sum(confidence_levels) / len(confidence_levels), 2) if confidence_levels else None
    return {
        "store_id": store_id,
        "ingredient_id": None,
        "ingredient_mode": "all_store_ingredients",
        "ingredient_count": len(forecast_items),
        "requested_ingredient_count": len(forecast_items) + len(errors),
        "forecast_start_date": min(starts) if starts else first_result.get("forecast_start_date"),
        "forecast_end_date": max(ends) if ends else first_result.get("forecast_end_date"),
        "last_actual_date": first_result.get("last_actual_date"),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "start_date_source": first_result.get("start_date_source"),
        "business_cutoff_rule": first_result.get("business_cutoff_rule"),
        "horizon": first_result.get("horizon") or {},
        "model_metadata": {
            "confidence_level": avg_confidence,
            "per_ingredient": {
                item["ingredient_id"]: item["result"].get("model_metadata", {})
                for item in forecast_items
            },
        },
        "summary": {
            "module": "inventory",
            "ingredient_mode": "all_store_ingredients",
            "ingredient_count": len(forecast_items),
            "forecast_count": total_forecast_count,
            "total_predicted_usage": round(total_predicted_usage, 2),
            "total_predicted_value": round(total_predicted_usage, 2),
            "average_predicted_usage": round(total_predicted_usage / total_forecast_count, 2) if total_forecast_count else 0.0,
            "per_ingredient": per_ingredient_summary,
        },
        "forecasts_by_ingredient": ingredient_results,
        **issue_summary,
    }


def _save_inventory_all_forecasts_atomically(payload, forecast_items, start_meta, errors=None, requested_ingredient_ids=None):
    errors = errors or []
    requested_ingredient_ids = requested_ingredient_ids or [item["ingredient_id"] for item in forecast_items]
    if not forecast_items:
        return {"status": "failed", "message": "Forecast kosong, tidak ada data untuk disimpan.", "saved_results": 0}

    all_rows = []
    starts = []
    ends = []
    train_starts = []
    train_ends = []
    training_rows = 0
    per_ingredient_metrics = {}
    per_ingredient_quality = {}
    per_ingredient_summary = []
    total_predicted_usage = 0.0

    for item in forecast_items:
        ingredient_id = item["ingredient_id"]
        result = item["result"]
        rows = _inventory_result_rows_for_backend(result, ingredient_id)
        all_rows.extend(rows)
        start_value, end_value = _inventory_forecast_bounds(result)
        if start_value:
            starts.append(str(start_value))
        if end_value:
            ends.append(str(end_value))

        training_info = item.get("training_info") or {}
        if training_info.get("train_start_date"):
            train_starts.append(training_info["train_start_date"])
        if training_info.get("train_end_date"):
            train_ends.append(training_info["train_end_date"])
        training_rows += int(training_info.get("training_rows") or 0)

        model_meta = result.get("model_metadata") or {}
        summary = result.get("summary") or {}
        per_ingredient_metrics[ingredient_id] = model_meta
        per_ingredient_quality[ingredient_id] = {
            "training_rows": int(training_info.get("training_rows") or 0),
            "train_start_date": training_info.get("train_start_date"),
            "train_end_date": training_info.get("train_end_date"),
            "data_days": model_meta.get("data_days"),
            "zero_ratio": model_meta.get("zero_ratio"),
            "outliers_nullified": model_meta.get("outliers_nullified"),
            "stockout_days_nullified": model_meta.get("stockout_days_nullified"),
        }
        total_value = float(summary.get("total_predicted_usage") or summary.get("total_predicted_value") or 0.0)
        total_predicted_usage += total_value
        per_ingredient_summary.append({
            "ingredient_id": ingredient_id,
            "forecast_count": len(result.get("forecasts") or []),
            "total_predicted_usage": round(total_value, 2),
            "average_predicted_usage": summary.get("average_predicted_usage"),
        })

    if not all_rows:
        return {"status": "failed", "message": "Forecast kosong, tidak ada result untuk disimpan.", "saved_results": 0}

    first_result = forecast_items[0]["result"]
    horizon = first_result.get("horizon") or {}
    horizon_label = horizon.get("label") or payload.get("horizon_label") or "daily"
    predict_start = min(starts) if starts else first_result.get("forecast_start_date")
    predict_end = max(ends) if ends else first_result.get("forecast_end_date")
    train_start = min(train_starts) if train_starts else datetime.now().date().isoformat()
    train_end = max(train_ends) if train_ends else datetime.now().date().isoformat()
    now = datetime.utcnow().isoformat() + "Z"

    issue_summary = _inventory_issue_summary(errors)
    skipped_ingredients = issue_summary["skipped_ingredients"]
    failed_ingredients = issue_summary["failed_ingredients"]
    skipped_ingredient_count = issue_summary["skipped_ingredient_count"]
    failed_ingredient_count = issue_summary["failed_ingredient_count"]
    unsuccessful_ingredient_count = issue_summary["unsuccessful_ingredient_count"]
    requested_ingredient_count = len(requested_ingredient_ids)
    partial_success = unsuccessful_ingredient_count > 0
    metrics = {
        "module": "inventory",
        "ingredient_mode": "all_store_ingredients",
        "ingredient_count": len(forecast_items),
        "successful_ingredient_count": len(forecast_items),
        "skipped_ingredient_count": skipped_ingredient_count,
        "failed_ingredient_count": failed_ingredient_count,
        "unsuccessful_ingredient_count": unsuccessful_ingredient_count,
        "requested_ingredient_count": requested_ingredient_count,
        "partial_success": partial_success,
        "skipped_ingredients": skipped_ingredients,
        "failed_ingredients": failed_ingredients,
        "warnings": skipped_ingredients,
        "errors": failed_ingredients,
        "per_ingredient": per_ingredient_metrics,
    }
    summary = {
        "module": "inventory",
        "ingredient_mode": "all_store_ingredients",
        "ingredient_count": len(forecast_items),
        "successful_ingredient_count": len(forecast_items),
        "skipped_ingredient_count": skipped_ingredient_count,
        "failed_ingredient_count": failed_ingredient_count,
        "unsuccessful_ingredient_count": unsuccessful_ingredient_count,
        "requested_ingredient_count": requested_ingredient_count,
        "partial_success": partial_success,
        "skipped_ingredients": skipped_ingredients,
        "failed_ingredients": failed_ingredients,
        "warnings": skipped_ingredients,
        "errors": failed_ingredients,
        "horizon_label": horizon_label,
        "forecast_start_date": predict_start,
        "forecast_end_date": predict_end,
        "start_date_source": first_result.get("start_date_source"),
        "last_actual_date": first_result.get("last_actual_date"),
        "business_cutoff_rule": first_result.get("business_cutoff_rule"),
        "forecast_count": len(all_rows),
        "total_predicted_usage": round(total_predicted_usage, 2),
        "total_predicted_value": round(total_predicted_usage, 2),
        "per_ingredient": per_ingredient_summary,
    }
    data_quality = {
        "date_range": {"start": train_start, "end": train_end},
        "training_rows": training_rows,
        "model_training_data_points": training_rows,
        "last_actual_date": first_result.get("last_actual_date") or train_end,
        "per_ingredient": per_ingredient_quality,
        "successful_ingredient_count": len(forecast_items),
        "skipped_ingredient_count": skipped_ingredient_count,
        "failed_ingredient_count": failed_ingredient_count,
        "unsuccessful_ingredient_count": unsuccessful_ingredient_count,
        "requested_ingredient_count": requested_ingredient_count,
        "partial_success": partial_success,
        "skipped_ingredients": skipped_ingredients,
        "failed_ingredients": failed_ingredients,
        "warnings": skipped_ingredients,
        "errors": failed_ingredients,
    }

    run_payload = {
        "store_id": payload["store_id"],
        "forecast_type": "inventory",
        "horizon_label": horizon_label,
        "horizon_days": int(horizon.get("days") or len(all_rows) or payload.get("horizon_count") or 1),
        "granularity": horizon_label,
        "model_name": "prophet",
        "model_version": "inventory-prophet-v2-calendar",
        "feature_version": "v2",
        "train_start_date": train_start,
        "train_end_date": train_end,
        "predict_start_date": predict_start,
        "predict_end_date": predict_end,
        "metrics": json.dumps(metrics),
        "summary": json.dumps(summary),
        "data_quality": json.dumps(data_quality),
        "status": "success",
        "started_at": now,
        "finished_at": now,
    }

    url = f"{Config.BACKEND_API_URL}/save"
    try:
        resp = requests.post(
            url,
            json={"run": run_payload, "results": all_rows},
            headers=Config.backend_headers(),
            timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        backend_response = resp.json()
        run_id = backend_response.get("run_id") or backend_response.get("data", {}).get("id")
        return {
            "status": "saved",
            "message": (
                "Forecast inventory sebagian ingredient berhasil disimpan ke backend; sebagian ingredient dilewati karena belum punya histori/model."
                if partial_success else
                "Forecast inventory semua ingredient berhasil disimpan ke backend."
            ),
            "run_id": run_id,
            "forecast_type": "inventory",
            "horizon_label": horizon_label,
            "horizon_days": run_payload["horizon_days"],
            "predict_start_date": predict_start,
            "predict_end_date": predict_end,
            "ingredient_count": len(forecast_items),
            "successful_ingredient_count": len(forecast_items),
            "skipped_ingredient_count": skipped_ingredient_count,
            "failed_ingredient_count": failed_ingredient_count,
            "unsuccessful_ingredient_count": unsuccessful_ingredient_count,
            "requested_ingredient_count": requested_ingredient_count,
            "skipped_ingredients": skipped_ingredients,
            "failed_ingredients": failed_ingredients,
            "warnings": skipped_ingredients,
            "errors": failed_ingredients,
            "partial_success": partial_success,
            "saved_results": len(all_rows),
            "backend_status": "success",
            "backend_response": backend_response,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "message": f"Gagal simpan forecast inventory semua ingredient: {exc}",
            "saved_results": 0,
            "backend_status": "failed",
        }


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
    """Preview forecast inventory tanpa menyimpan ke database.

    Jika ingredient_id tidak dikirim, endpoint menjalankan forecast untuk semua
    ingredient milik store_id tersebut.
    """
    try:
        raw_payload = _get_request_json()
        payload = _parse_inventory_standard_body(raw_payload)
        freq = _map_horizon_to_freq(payload["horizon_label"])
        start_meta = asyncio.run(_resolve_inventory_start_date_meta(
            payload["store_id"],
            payload["horizon_label"],
            payload.get("start_date"),
        ))

        forecast_items, errors, ingredient_ids = asyncio.run(_run_inventory_forecasts_from_payload(payload, freq, start_meta))
        result = _aggregate_inventory_response(payload["store_id"], payload, forecast_items, errors=errors)

        response_payload = dict(payload)
        response_payload["start_date"] = start_meta["start_date"]
        response_payload["start_date_mode"] = start_meta.get("start_date_mode", "auto")
        if not response_payload.get("ingredient_id"):
            response_payload["ingredient_count"] = len(ingredient_ids)

        status = "partial_success" if errors else "success"
        status_code = 207 if errors else 200
        message = (
            f"Preview forecast inventory {payload['horizon_label']} berhasil untuk {len(forecast_items)} dari {len(ingredient_ids)} ingredient."
            if not payload.get("ingredient_id")
            else f"Preview forecast inventory {payload['horizon_label']} berhasil."
        )
        return jsonify(_standard_inventory_response(
            result,
            response_payload,
            message,
            status=status,
        )), status_code
    except FileNotFoundError:
        return jsonify({"detail": "Model inventory belum di-training"}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500


@app.route('/api/forecast/inventory/save', methods=['POST'])
def inventory_save():
    """Generate + simpan forecast inventory ke database.

    Jika ingredient_id tidak dikirim, endpoint menjalankan semua ingredient milik
    store_id. Default save all menyimpan ingredient yang berhasil dan melaporkan
    ingredient yang gagal sebagai skipped/failed. Kirim allow_partial=false bila
    ingin mode strict all-or-nothing.
    """
    try:
        raw_payload = _get_request_json()
        payload = _parse_inventory_standard_body(raw_payload)
        allow_partial = bool(raw_payload.get("allow_partial", not bool(payload.get("ingredient_id"))))
        freq = _map_horizon_to_freq(payload["horizon_label"])
        start_meta = asyncio.run(_resolve_inventory_start_date_meta(
            payload["store_id"],
            payload["horizon_label"],
            payload.get("start_date"),
        ))

        forecast_items, errors, ingredient_ids = asyncio.run(_run_inventory_forecasts_from_payload(payload, freq, start_meta))

        if payload.get("ingredient_id"):
            forecaster = forecast_items[0]["forecaster"]
            result = forecast_items[0]["result"]
            save_result = forecaster.save_all_forecasts(
                periods=payload["horizon_count"],
                freq=freq,
                start_date=start_meta["start_date"],
                forecast_result=result,
                start_date_source=start_meta.get("start_date_source"),
                business_cutoff_rule=start_meta.get("business_cutoff_rule"),
                last_actual_date=start_meta.get("latest_complete_day"),
            )
        else:
            if errors and not allow_partial:
                issue_summary = _inventory_issue_summary(errors)
                return jsonify({
                    "detail": "Sebagian ingredient tidak bisa diprediksi; forecast inventory semua ingredient tidak disimpan karena allow_partial=false.",
                    "skipped_ingredients": issue_summary["skipped_ingredients"],
                    "failed_ingredients": issue_summary["failed_ingredients"],
                    "warnings": issue_summary["warnings"],
                    "errors": issue_summary["errors"],
                    "successful_ingredient_count": len(forecast_items),
                    "skipped_ingredient_count": issue_summary["skipped_ingredient_count"],
                    "failed_ingredient_count": issue_summary["failed_ingredient_count"],
                    "unsuccessful_ingredient_count": issue_summary["unsuccessful_ingredient_count"],
                    "requested_ingredient_count": len(ingredient_ids),
                    "hint": "Tambahkan histori stok lalu retrain, atau pakai allow_partial=true.",
                }), 400
            result = _aggregate_inventory_response(payload["store_id"], payload, forecast_items, errors=errors)
            save_result = _save_inventory_all_forecasts_atomically(
                payload,
                forecast_items,
                start_meta,
                errors=errors,
                requested_ingredient_ids=ingredient_ids,
            )

        if save_result.get("status") != "saved":
            return jsonify({"detail": save_result.get("message", "Gagal menyimpan forecast inventory"), "save_result": save_result}), 500

        response_payload = dict(payload)
        response_payload["start_date"] = start_meta["start_date"]
        response_payload["start_date_mode"] = start_meta.get("start_date_mode", "auto")
        if not response_payload.get("ingredient_id"):
            response_payload["ingredient_count"] = len(ingredient_ids)

        status = "partial_success" if errors else "success"
        status_code = 201
        message = (
            f"Forecast inventory {payload['horizon_label']} berhasil disimpan untuk {len(forecast_items)} dari {len(ingredient_ids)} ingredient."
            if not payload.get("ingredient_id")
            else f"Forecast inventory {payload['horizon_label']} berhasil disimpan ke database."
        )
        return jsonify(_standard_inventory_response(
            result,
            response_payload,
            message,
            save_result=public_save_result(save_result),
            status=status,
        )), status_code
    except FileNotFoundError:
        return jsonify({"detail": "Model inventory belum di-training"}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)