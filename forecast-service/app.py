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

# Scheduler untuk retrain otomatis
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

# ============================================
# SCHEDULER: Retrain otomatis tiap Minggu 02:00
# ============================================
def scheduled_train():
    """Wrapper untuk scheduler, tanpa task_id."""
    train_all_inventory_models(task_id=None)

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=scheduled_train,
    trigger="cron",
    day_of_week="sun",
    hour=2,
    minute=0
)

def scheduled_visitors_retrain():
    """Retrain periodic untuk visitors."""
    store_ids = visitors_trainer.list_trained_stores()
    for store_id in store_ids:
        try:
            asyncio.run(visitors_forecast_service.retrain(store_id=store_id, force=True))
        except Exception as e:
            traceback.print_exc()

scheduler.add_job(
    func=scheduled_visitors_retrain,
    trigger="interval",
    days=Config.VISITORS_RETRAIN_INTERVAL_DAYS,
    id="visitors_auto_retrain",
    replace_existing=True
)

scheduler.start()
atexit.register(lambda: scheduler.shutdown())

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

@app.route('/api/forecast/visitors/daily', methods=['POST'])
def visitors_predict():
    req = request.get_json()
    if not req or 'store_id' not in req:
        return jsonify({"detail": "store_id wajib diisi"}), 400
    
    store_id = req['store_id']
    forecast_days = int(req.get('forecast_days', Config.VISITORS_FORECAST_HORIZON_DAYS))
    start_date_str = req.get('start_date')
    start_date_val = date.fromisoformat(start_date_str) if start_date_str else None

    try:
        result = asyncio.run(visitors_forecast_service.forecast(
            store_id=store_id,
            forecast_days=forecast_days,
            start_date=start_date_val
        ))
        return jsonify(_json_model(result)), 200
    except FileNotFoundError as e:
        return jsonify({"detail": str(e)}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500

@app.route('/api/forecast/visitors/predict-weekly', methods=['POST'])
def visitors_predict_weekly():
    req = request.get_json()
    if not req or 'store_id' not in req:
        return jsonify({"detail": "store_id wajib diisi"}), 400
    
    store_id = req['store_id']
    forecast_weeks = int(req.get('forecast_weeks', 4))
    start_date_str = req.get('start_date')
    start_date_val = date.fromisoformat(start_date_str) if start_date_str else None

    try:
        result = asyncio.run(visitors_forecast_service.forecast_weekly(
            store_id=store_id,
            forecast_weeks=forecast_weeks,
            start_date=start_date_val
        ))
        return jsonify(_json_model(result)), 200
    except FileNotFoundError as e:
        return jsonify({"detail": str(e)}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500

@app.route('/api/forecast/visitors/predict-monthly', methods=['POST'])
def visitors_predict_monthly():
    req = request.get_json()
    if not req or 'store_id' not in req:
        return jsonify({"detail": "store_id wajib diisi"}), 400
    
    store_id = req['store_id']
    forecast_months = int(req.get('forecast_months', 3))
    start_date_str = req.get('start_date')
    start_date_val = date.fromisoformat(start_date_str) if start_date_str else None

    try:
        result = asyncio.run(visitors_forecast_service.forecast_monthly(
            store_id=store_id,
            forecast_months=forecast_months,
            start_date=start_date_val
        ))
        return jsonify(_json_model(result)), 200
    except FileNotFoundError as e:
        return jsonify({"detail": str(e)}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500


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
# ROUTE MODUL SALES (NEW STANDARD ROUTES)
# ============================================

async def _run_sales_forecast_from_payload(payload):
    store_id = _get_store_id(payload)
    if not store_id:
        raise ValueError("store_id wajib diisi")

    horizon_label = _parse_horizon_label(payload)
    horizon_count = _parse_horizon_count(payload, horizon_label)
    start_date_val = _parse_start_date(payload)

    if horizon_label == "daily":
        result = await sales_forecast_service.forecast(
            store_id=store_id,
            forecast_days=horizon_count,
            start_date=start_date_val or date.today(),
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

    response = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    response["request_meta"] = {
        "module": "sales",
        "horizon_label": horizon_label,
        "horizon_count": horizon_count,
        "mode": "preview",
        "saved_to_database": False,
    }
    return response

@app.route('/api/forecast/sales/preview', methods=['POST'])
def sales_preview():
    payload = _get_request_json()
    try:
        result = asyncio.run(_run_sales_forecast_from_payload(payload))
        return jsonify(result), 200
    except FileNotFoundError as e:
        return jsonify({"detail": str(e)}), 404
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500

@app.route('/api/forecast/sales/save', methods=['POST'])
def sales_save():
    payload = _get_request_json()
    backend_token = payload.get("backend_token", "")
    forecast_data = payload.get("forecast")
    if not forecast_data:
        return jsonify({"detail": "field 'forecast' wajib diisi untuk save"}), 400
    
    store_id = forecast_data.get("store_id")
    if not store_id:
        return jsonify({"detail": "store_id wajib diisi"}), 400

    try:
        success, message = asyncio.run(sales_forecast_service.save_forecast_to_db(store_id, forecast_data, backend_token))
        if success:
            return jsonify({"success": True, "message": message}), 200
        else:
            return jsonify({"success": False, "detail": message}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Internal server error: {str(e)}"}), 500

@app.route('/api/forecast/sales/run', methods=['POST'])
def sales_run():
    payload = _get_request_json()
    backend_token = payload.get("backend_token", "")
    
    try:
        result = asyncio.run(_run_sales_forecast_from_payload(payload))
        
        # Override mode for saving
        result["request_meta"]["mode"] = "run"
        result["request_meta"]["saved_to_database"] = True
        
        store_id = _get_store_id(payload)
        success, message = asyncio.run(sales_forecast_service.save_forecast_to_db(store_id, result, backend_token))
        
        if success:
            return jsonify(result), 200
        else:
            return jsonify({"detail": message}), 500
            
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
        return jsonify({"error": "Task tidak ditemukan"}), 404
    return jsonify(task)

@app.route('/api/forecast/inventory/preview', methods=['POST'])
def inventory_preview():
    """Preview forecast tanpa menyimpan ke database."""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        ingredient_id = data.get('ingredient_id')
        horizon_label = data.get('horizon_label', 'weekly').lower()
        horizon_count = int(data.get('horizon_count', 4))
        start_date = data.get('start_date')

        if not store_id or not ingredient_id:
            return jsonify({"error": "store_id dan ingredient_id wajib"}), 400

        freq = _map_horizon_to_freq(horizon_label)
        periods = horizon_count

        forecaster = InventoryForecaster(store_id, ingredient_id, freq)
        result = forecaster.predict(periods=periods, freq=freq, start_date=start_date)

        return jsonify({
            "status": "success",
            "message": f"Preview forecast {horizon_label} berhasil",
            "data": result,
            "request": {
                "store_id": store_id,
                "ingredient_id": ingredient_id,
                "horizon_label": horizon_label,
                "horizon_count": horizon_count,
                "start_date": start_date,
                "start_date_mode": "custom" if start_date else "auto"
            }
        })
    except FileNotFoundError:
        return jsonify({"error": "Model belum di-training"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/forecast/inventory/save', methods=['POST'])
def inventory_save():
    """Simpan hasil forecast ke database."""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        ingredient_id = data.get('ingredient_id')
        horizon_label = data.get('horizon_label', 'weekly').lower()
        horizon_count = int(data.get('horizon_count', 4))
        start_date = data.get('start_date')

        if not store_id or not ingredient_id:
            return jsonify({"error": "store_id dan ingredient_id wajib"}), 400

        freq = _map_horizon_to_freq(horizon_label)
        periods = horizon_count

        forecaster = InventoryForecaster(store_id, ingredient_id, freq)
        success = forecaster.save_all_forecasts(periods=periods, freq=freq, start_date=start_date)

        if success:
            return jsonify({
                "status": "success",
                "message": f"Forecast {horizon_label} berhasil disimpan ke database"
            })
        else:
            return jsonify({"error": "Gagal menyimpan forecast"}), 500
    except FileNotFoundError:
        return jsonify({"error": "Model belum di-training"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/forecast/inventory/run', methods=['POST'])
def inventory_run():
    """Preview + simpan ke database."""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        ingredient_id = data.get('ingredient_id')
        horizon_label = data.get('horizon_label', 'weekly').lower()
        horizon_count = int(data.get('horizon_count', 4))
        start_date = data.get('start_date')

        if not store_id or not ingredient_id:
            return jsonify({"error": "store_id dan ingredient_id wajib"}), 400

        freq = _map_horizon_to_freq(horizon_label)
        periods = horizon_count

        forecaster = InventoryForecaster(store_id, ingredient_id, freq)
        # Dapatkan prediksi dulu
        result = forecaster.predict(periods=periods, freq=freq, start_date=start_date)
        # Simpan ke database
        success = forecaster.save_all_forecasts(periods=periods, freq=freq, start_date=start_date)

        return jsonify({
            "status": "success" if success else "error",
            "message": f"Forecast {horizon_label} {'berhasil dijalankan dan disimpan.' if success else 'gagal disimpan.'}",
            "data": result,
            "request": {
                "store_id": store_id,
                "ingredient_id": ingredient_id,
                "horizon_label": horizon_label,
                "horizon_count": horizon_count,
                "start_date": start_date,
                "start_date_mode": "custom" if start_date else "auto"
            },
            "save_result": {
                "status": "saved" if success else "failed",
                "saved_results": len(result.get('forecasts', []))
            } if success else None
        })
    except FileNotFoundError:
        return jsonify({"error": "Model belum di-training"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)