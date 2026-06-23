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
        return jsonify(result.model_dump() if hasattr(result, "model_dump") else result.dict()), 200
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
            "request": {
                "store_id": payload["store_id"],
                "horizon_label": payload["horizon_label"],
                "horizon_count": payload["horizon_count"],
            },
            "data": _json_model(result),
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
            "request": {
                "store_id": payload["store_id"],
                "horizon_label": payload["horizon_label"],
                "horizon_count": payload["horizon_count"],
            },
            "save_result": save_result,
            "data": _json_model(forecast_result),
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
            "request": {
                "store_id": payload["store_id"],
                "horizon_label": payload["horizon_label"],
                "horizon_count": payload["horizon_count"],
            },
            "save_result": save_result,
            "data": _json_model(forecast_result),
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
    start_date_val = date.fromisoformat(start_date_str) if start_date_str else date.today()

    try:
        result = asyncio.run(visitors_forecast_service.forecast(
            store_id=store_id,
            forecast_days=forecast_days,
            start_date=start_date_val
        ))
        return jsonify(result.model_dump() if hasattr(result, "model_dump") else result.dict()), 200
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
        return jsonify(result.model_dump() if hasattr(result, "model_dump") else result.dict()), 200
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
        return jsonify(result.model_dump() if hasattr(result, "model_dump") else result.dict()), 200
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
        return jsonify(result.model_dump() if hasattr(result, "model_dump") else result.dict()), 200
    except ValueError as e:
        return jsonify({"detail": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"detail": f"Retrain gagal: {str(e)}"}), 500

# ============================================
# ROUTE INVENTORY (STOK BARANG)
# ============================================

@app.route('/api/inventory/forecast', methods=['POST'])
def forecast_inventory():
    """
    Mendapatkan forecast stok bahan baku.
    Request JSON:
    {
        "store_id": "...",
        "ingredient_id": "...",
        "periods": 4,
        "freq": "W"   // "D", "W", atau "M"
    }
    """
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        ingredient_id = data.get('ingredient_id')
        periods = int(data.get('periods', 1))
        freq = data.get('freq', 'W').upper()

        if not store_id or not ingredient_id:
            return jsonify({"error": "store_id dan ingredient_id wajib diisi"}), 400
        if freq not in ['D', 'W', 'M']:
            return jsonify({"error": "freq harus 'D', 'W', atau 'M'"}), 400

        forecaster = InventoryForecaster(store_id, ingredient_id)
        result = forecaster.predict(periods=periods, freq=freq)

        return jsonify({
            "success": True,
            "message": f"Forecast {freq} untuk {periods} periode ke depan",
            "data": result
        })

    except FileNotFoundError:
        return jsonify({
            "error": "Model belum di-training. Silakan panggil endpoint /api/inventory/train/start terlebih dahulu."
        }), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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


# Backward compatibility – langsung jalankan async tanpa perlu task_id
@app.route('/api/inventory/train', methods=['POST'])
def train_inventory():
    """(Deprecated) Langsung mulai training async."""
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
        "message": "Training dimulai. Gunakan /api/inventory/train/status/<task_id> untuk memantau."
    })

@app.route('/api/inventory/save-all-forecasts', methods=['POST'])
def save_all_forecasts():
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        ingredient_id = data.get('ingredient_id')
        periods = int(data.get('periods', 4))
        freq = data.get('freq', 'W').upper()
        if not store_id or not ingredient_id:
            return jsonify({"error": "store_id dan ingredient_id wajib"}), 400
        fc = InventoryForecaster(store_id, ingredient_id)
        success = fc.save_all_forecasts(periods=periods, freq=freq)
        if success:
            return jsonify({"status": "sukses", "pesan": "Semua forecast tersimpan"})
        else:
            return jsonify({"error": "Gagal menyimpan"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/inventory/save-all-existing', methods=['POST'])
def save_all_existing_forecasts():
    """Menyimpan ulang forecast untuk semua pasangan yang sudah punya model."""
    model_dir = os.path.join(Config.MODEL_DIR, 'inventory')
    if not os.path.isdir(model_dir):
        return jsonify({"error": "Folder model tidak ditemukan"}), 500

    pkl_files = [f for f in os.listdir(model_dir) if f.endswith('.pkl')]
    if not pkl_files:
        return jsonify({"error": "Tidak ada model tersimpan"}), 404

    results = []
    for filename in pkl_files:
        # Nama file: model_store{store_id}_ingr{ingredient_id}.pkl
        name_part = filename[len("model_store"):].replace('.pkl', '')
        store_id, ingredient_id = name_part.split('_ingr')
        
        try:
            fc = InventoryForecaster(store_id, ingredient_id)
            fc.load_model()
            fc.save_all_forecasts(periods=4, freq='W')
            results.append({"pair": f"{store_id}/{ingredient_id}", "status": "saved"})
        except Exception as e:
            results.append({"pair": f"{store_id}/{ingredient_id}", "status": "error", "error": str(e)})

    return jsonify({"status": "selesai", "details": results})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)