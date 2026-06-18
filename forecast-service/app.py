from flask import Flask, request, jsonify
from config import Config
import os
import traceback
import uuid
import threading
import sys
import asyncio
import calendar
import glob
from datetime import datetime, date, timedelta

from modules.visitors.forecaster import forecast_service as visitors_forecast_service
from modules.visitors.trainer import trainer as visitors_trainer
from modules.visitors.forecaster import golang_client

# Import modul inventory
from modules.inventory.forecaster import InventoryForecaster
from modules.inventory.trainer import train_all_inventory_models, training_tasks

# Import modul Sales
from modules.sales.forecaster import SalesForecaster
from modules.sales.trainer import train_all as train_all_sales

sales_training_tasks = {}
sales_forecaster = SalesForecaster()
sales_forecaster.load_models()

def background_sales_training(task_id):
    try:
        sales_training_tasks[task_id]["status"] = "TRAINING"
        sales_training_tasks[task_id]["message"] = "Proses training Global Model Sales sedang berjalan..."
        train_all_sales()
        sales_forecaster.load_models()
        sales_training_tasks[task_id]["status"] = "COMPLETED"
        sales_training_tasks[task_id]["message"] = "Training Global Model Sales selesai."
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

if Config.FORECAST_MODE == "scheduler" and Config.ENABLE_FORECAST_SCHEDULER:
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    print("[scheduler] Forecast scheduler aktif.")
else:
    print("[scheduler] Forecast scheduler nonaktif. Set FORECAST_MODE=scheduler dan ENABLE_FORECAST_SCHEDULER=true untuk mengaktifkan.")

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



# ============================================
# FINAL FORECAST API STANDARD
# ============================================
VALID_FORECAST_MODULES = {"sales", "visitors", "inventory"}
VALID_HORIZON_LABELS = {"weekly", "monthly"}


def _json_safe(value):
    """Convert common Python/Pandas values into Flask JSON-safe values."""
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if hasattr(value, "dict") and callable(value.dict):
        return _json_safe(value.dict())
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "isoformat") and value.__class__.__name__ in {"Timestamp", "datetime64"}:
        return value.isoformat()
    return value


def _success(message, data=None, status=200):
    return jsonify({"success": True, "message": message, "data": _json_safe(data or {})}), status


def _error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def _request_json():
    return request.get_json(silent=True) or {}


def _normalize_store_id(req):
    """API final memakai store_id. m_store_id tetap diterima sebagai legacy fallback."""
    return req.get("store_id") or req.get("m_store_id")


def _parse_force(req):
    value = req.get("force", False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _parse_modules(req):
    modules = req.get("modules")
    if modules in (None, "", []):
        return ["sales", "visitors", "inventory"]
    if isinstance(modules, str):
        modules = [m.strip() for m in modules.split(",") if m.strip()]
    if not isinstance(modules, list):
        raise ValueError("modules harus berupa array atau string dipisahkan koma")
    modules = [str(m).strip().lower() for m in modules]
    invalid = [m for m in modules if m not in VALID_FORECAST_MODULES]
    if invalid:
        raise ValueError(f"modules tidak valid: {invalid}. allowed: sales, visitors, inventory")
    return modules


def _parse_horizon(req):
    horizon_label = str(req.get("horizon_label", "weekly")).strip().lower()
    if horizon_label not in VALID_HORIZON_LABELS:
        raise ValueError("invalid horizon_label, allowed values: weekly, monthly")

    today = date.today()
    start_date_str = req.get("start_date")
    if start_date_str:
        start_date = date.fromisoformat(start_date_str)
    elif horizon_label == "monthly":
        # default monthly: awal bulan depan
        year = today.year + (1 if today.month == 12 else 0)
        month = 1 if today.month == 12 else today.month + 1
        start_date = date(year, month, 1)
    else:
        # default weekly: besok / 7 hari ke depan dari proses dibuat
        start_date = today + timedelta(days=1)

    if horizon_label == "weekly":
        horizon_days = 7
    else:
        horizon_days = calendar.monthrange(start_date.year, start_date.month)[1]

    predict_end_date = start_date + timedelta(days=horizon_days - 1)
    return horizon_label, horizon_days, start_date, predict_end_date


def _extract_daily_rows_from_sales_raw(raw_rows):
    rows = []
    for item in raw_rows:
        target = item["date"]
        predicted = float(item.get("p", 0) or 0)
        std = float(item.get("s", 0) or 0)
        lower = max(0, predicted - (1.96 * std))
        upper = predicted + (1.96 * std)
        rows.append({
            "target_date": target.strftime("%Y-%m-%d") if hasattr(target, "strftime") else str(target),
            "predicted_value": round(predicted, 2),
            "lower_bound": round(lower, 2),
            "upper_bound": round(upper, 2),
        })
    return rows


def _run_sales_forecast(req):
    store_id = _normalize_store_id(req)
    if not store_id:
        return None, "store_id wajib diisi", 400

    horizon_label, horizon_days, start_date, predict_end_date = _parse_horizon(req)
    raw_rows, err = sales_forecaster._predict_days(store_id, horizon_days)
    if err and not isinstance(err, dict):
        return None, err, 404

    rows = _extract_daily_rows_from_sales_raw(raw_rows or [])
    total = sum(float(x.get("predicted_value", 0) or 0) for x in rows)
    data = {
        "store_id": store_id,
        "module": "sales",
        "horizon_label": horizon_label,
        "horizon_days": horizon_days,
        "granularity": "daily",
        "predict_start_date": rows[0]["target_date"] if rows else start_date.isoformat(),
        "predict_end_date": rows[-1]["target_date"] if rows else predict_end_date.isoformat(),
        "run_id": None,
        "results_count": len(rows),
        "summary": {
            "total_predicted_value": round(total, 2),
            "average_daily_value": round(total / len(rows), 2) if rows else 0,
        },
        "metrics": err if isinstance(err, dict) else {},
        "results": rows,
    }
    return data, None, 200


def _run_visitors_forecast(req):
    store_id = _normalize_store_id(req)
    if not store_id:
        return None, "store_id wajib diisi", 400

    horizon_label, horizon_days, start_date, predict_end_date = _parse_horizon(req)
    try:
        result = asyncio.run(visitors_forecast_service.forecast(
            store_id=store_id,
            forecast_days=horizon_days,
            start_date=start_date,
        ))
        result_dict = _json_safe(result)
        forecasts = result_dict.get("forecasts", [])
        rows = []
        for item in forecasts:
            rows.append({
                "target_date": item.get("date"),
                "predicted_value": item.get("predicted_visitors", 0),
                "predicted_transactions": item.get("predicted_transactions", 0),
                "lower_bound": item.get("lower_bound"),
                "upper_bound": item.get("upper_bound"),
            })
        data = {
            "store_id": store_id,
            "module": "visitors",
            "horizon_label": horizon_label,
            "horizon_days": horizon_days,
            "granularity": "daily",
            "predict_start_date": rows[0]["target_date"] if rows else start_date.isoformat(),
            "predict_end_date": rows[-1]["target_date"] if rows else predict_end_date.isoformat(),
            "run_id": None,
            "results_count": len(rows),
            "model_metadata": result_dict.get("model_metadata"),
            "results": rows,
        }
        return data, None, 200
    except FileNotFoundError as e:
        return None, str(e), 404
    except ValueError as e:
        return None, str(e), 400
    except Exception as e:
        traceback.print_exc()
        return None, f"Internal server error: {str(e)}", 500


def _inventory_model_pairs_for_store(store_id):
    model_dir = os.path.join(Config.MODEL_DIR, "inventory")
    pattern = os.path.join(model_dir, f"model_store{store_id}_ingr*.pkl")
    pairs = []
    for path in glob.glob(pattern):
        filename = os.path.basename(path)
        if not filename.startswith(f"model_store{store_id}_ingr"):
            continue
        ingredient_id = filename[len(f"model_store{store_id}_ingr"):-len(".pkl")]
        if ingredient_id:
            pairs.append(ingredient_id)
    return sorted(set(pairs))


def _run_inventory_for_ingredient(store_id, ingredient_id, horizon_days):
    forecaster = InventoryForecaster(store_id, ingredient_id)
    result = forecaster.predict(periods=horizon_days, freq="D")
    rows = []
    for item in result.get("daily_forecast", []):
        rows.append({
            "target_date": item.get("date"),
            "item_id": ingredient_id,
            "item_type": "ingredient",
            "predicted_value": item.get("predicted_usage", 0),
            "lower_bound": item.get("lower_bound"),
            "upper_bound": item.get("upper_bound"),
        })
    return rows, result


def _run_inventory_forecast(req):
    store_id = _normalize_store_id(req)
    if not store_id:
        return None, "store_id wajib diisi", 400

    horizon_label, horizon_days, start_date, predict_end_date = _parse_horizon(req)
    ingredient_id = req.get("ingredient_id")

    try:
        ingredient_ids = [ingredient_id] if ingredient_id else _inventory_model_pairs_for_store(store_id)
        if not ingredient_ids:
            return None, "Model inventory untuk store ini belum ditemukan. Jalankan retrain inventory terlebih dahulu atau isi ingredient_id tertentu.", 404

        all_results = []
        details = []
        for ingr_id in ingredient_ids:
            rows, raw = _run_inventory_for_ingredient(store_id, ingr_id, horizon_days)
            all_results.extend(rows)
            details.append({
                "ingredient_id": ingr_id,
                "results_count": len(rows),
                "summary": raw.get("forecast_summary", {}),
                "model_confidence": raw.get("model_confidence", {}),
            })

        data = {
            "store_id": store_id,
            "module": "inventory",
            "horizon_label": horizon_label,
            "horizon_days": horizon_days,
            "granularity": "daily",
            "predict_start_date": all_results[0]["target_date"] if all_results else start_date.isoformat(),
            "predict_end_date": all_results[-1]["target_date"] if all_results else predict_end_date.isoformat(),
            "run_id": None,
            "results_count": len(all_results),
            "ingredient_count": len(ingredient_ids),
            "ingredients": details,
            "results": all_results,
        }
        return data, None, 200
    except FileNotFoundError as e:
        return None, str(e), 404
    except ValueError as e:
        return None, str(e), 400
    except Exception as e:
        traceback.print_exc()
        return None, str(e), 500


def _run_module_forecast(module, req):
    module = module.lower().strip()
    if module == "sales":
        return _run_sales_forecast(req)
    if module == "visitors":
        return _run_visitors_forecast(req)
    if module == "inventory":
        return _run_inventory_forecast(req)
    return None, "module tidak valid, allowed values: sales, visitors, inventory", 400


def _start_threaded_task(task_store, start_message, target, *args):
    task_id = str(uuid.uuid4())
    with threading.Lock():
        task_store[task_id] = {"status": "STARTING", "message": start_message}
    thread = threading.Thread(target=target, args=(task_id, *args), daemon=True)
    thread.start()
    return task_id


def _background_inventory_training(task_id, store_id=None, ingredient_id=None):
    try:
        training_tasks[task_id]["status"] = "TRAINING"
        training_tasks[task_id]["message"] = "Training inventory berjalan..."
        if ingredient_id:
            fc = InventoryForecaster(store_id, ingredient_id)
            fc.tune_and_train()
        else:
            # Untuk saat ini trainer existing memproses semua pasangan dari backend.
            # Route final sudah siap menerima store_id; filtering store-specific bisa ditambahkan di fase berikutnya.
            train_all_inventory_models(task_id=task_id)
        training_tasks[task_id]["status"] = "COMPLETED"
        training_tasks[task_id]["message"] = "Training inventory selesai."
    except Exception as e:
        traceback.print_exc()
        training_tasks[task_id]["status"] = "ERROR"
        training_tasks[task_id]["message"] = str(e)


@app.route('/api/forecast/<module>/run', methods=['POST'])
def forecast_module_run(module):
    req = _request_json()
    if module not in VALID_FORECAST_MODULES:
        return _error("module tidak valid, allowed values: sales, visitors, inventory", 400)
    try:
        data, err, status = _run_module_forecast(module, req)
        if err:
            return _error(err, status)
        return _success("Forecast completed", data, status)
    except ValueError as e:
        return _error(str(e), 400)


@app.route('/api/forecast/run-all', methods=['POST'])
def forecast_run_all():
    req = _request_json()
    store_id = _normalize_store_id(req)
    if not store_id:
        return _error("store_id wajib diisi", 400)
    try:
        modules = _parse_modules(req)
        horizon_label, horizon_days, _, _ = _parse_horizon(req)
    except ValueError as e:
        return _error(str(e), 400)

    results = {}
    overall_status = 200
    for module in modules:
        data, err, status = _run_module_forecast(module, req)
        if err:
            overall_status = max(overall_status, status)
            results[module] = {"status": "error", "error": err}
        else:
            results[module] = {
                "status": "success",
                "run_id": data.get("run_id"),
                "results_count": data.get("results_count", 0),
                "horizon_days": data.get("horizon_days", horizon_days),
            }

    return _success("All forecasts processed", {
        "store_id": store_id,
        "horizon_label": horizon_label,
        "modules": results,
    }, 207 if any(v.get("status") == "error" for v in results.values()) else overall_status)


@app.route('/api/forecast/sales/retrain', methods=['POST'])
def forecast_sales_retrain_standard():
    req = _request_json()
    store_id = _normalize_store_id(req)
    if not store_id:
        return _error("store_id wajib diisi", 400)
    task_id = _start_threaded_task(sales_training_tasks, "Persiapan training sales...", background_sales_training)
    return _success("Sales retrain started", {"store_id": store_id, "task_id": task_id, "note": "Model sales saat ini masih global; store_id dicatat untuk kontrak API."}, 202)


@app.route('/api/forecast/inventory/retrain', methods=['POST'])
def forecast_inventory_retrain_standard():
    req = _request_json()
    store_id = _normalize_store_id(req)
    if not store_id:
        return _error("store_id wajib diisi", 400)
    ingredient_id = req.get("ingredient_id")
    task_id = str(uuid.uuid4())
    with threading.Lock():
        training_tasks[task_id] = {"status": "STARTING", "message": "Persiapan training inventory..."}
    thread = threading.Thread(target=_background_inventory_training, args=(task_id, store_id, ingredient_id), daemon=True)
    thread.start()
    return _success("Inventory retrain started", {"store_id": store_id, "ingredient_id": ingredient_id, "task_id": task_id}, 202)


@app.route('/api/forecast/retrain-all', methods=['POST'])
def forecast_retrain_all_standard():
    req = _request_json()
    store_id = _normalize_store_id(req)
    if not store_id:
        return _error("store_id wajib diisi", 400)
    try:
        modules = _parse_modules(req)
    except ValueError as e:
        return _error(str(e), 400)

    tasks = {}
    if "sales" in modules:
        tasks["sales"] = {"task_id": _start_threaded_task(sales_training_tasks, "Persiapan training sales...", background_sales_training), "status": "started"}
    if "visitors" in modules:
        try:
            force = _parse_force(req)
            result = asyncio.run(visitors_forecast_service.retrain(store_id=store_id, force=force))
            tasks["visitors"] = {"status": "completed", "result": _json_safe(result)}
        except Exception as e:
            traceback.print_exc()
            tasks["visitors"] = {"status": "error", "error": str(e)}
    if "inventory" in modules:
        task_id = str(uuid.uuid4())
        with threading.Lock():
            training_tasks[task_id] = {"status": "STARTING", "message": "Persiapan training inventory..."}
        thread = threading.Thread(target=_background_inventory_training, args=(task_id, store_id, req.get("ingredient_id")), daemon=True)
        thread.start()
        tasks["inventory"] = {"task_id": task_id, "status": "started"}

    return _success("Retrain all processed", {"store_id": store_id, "modules": tasks}, 202)


# Legacy compatibility untuk nama route visitors yang pernah dipakai saat testing.
@app.route('/api/forecast/visitors/weekly', methods=['POST'])
def visitors_weekly_legacy_wrapper():
    req = _request_json()
    req["horizon_label"] = "weekly"
    data, err, status = _run_visitors_forecast(req)
    if err:
        return _error(err, status)
    return _success("Forecast completed", data, status)


@app.route('/api/forecast/visitors/monthly', methods=['POST'])
def visitors_monthly_legacy_wrapper():
    req = _request_json()
    req["horizon_label"] = "monthly"
    data, err, status = _run_visitors_forecast(req)
    if err:
        return _error(err, status)
    return _success("Forecast completed", data, status)

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
    req = _request_json()
    store_id = _normalize_store_id(req)
    if not store_id:
        return _error("store_id wajib diisi", 400)

    force = _parse_force(req)

    try:
        result = asyncio.run(visitors_forecast_service.retrain(
            store_id=store_id,
            force=force
        ))
        return _success("Visitors retrain completed", {
            "store_id": store_id,
            "module": "visitors",
            "force": force,
            "result": _json_safe(result),
        }, 200)
    except ValueError as e:
        return _error(str(e), 400)
    except Exception as e:
        traceback.print_exc()
        return _error(f"Retrain gagal: {str(e)}", 500)

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

# ============================================
# ROUTE MODUL SALES (TRAINING)
# ============================================

@app.route('/api/forecast/train/start', methods=['POST'])
def start_sales_training():
    task_id = str(uuid.uuid4())
    with threading.Lock():
        sales_training_tasks[task_id] = {
            "status": "STARTING",
            "message": "Persiapan training sales..."
        }
    
    thread = threading.Thread(target=background_sales_training, args=(task_id,))
    thread.start()
    
    return jsonify({
        "task_id": task_id,
        "message": "Training Sales dimulai. Pantau progress di /api/forecast/train/status/<task_id>"
    })

@app.route('/api/forecast/train/status/<task_id>', methods=['GET'])
def get_sales_training_status(task_id):
    task = sales_training_tasks.get(task_id)
    if not task: return jsonify({"error": "Task tidak ditemukan"}), 404
    return jsonify(task)


# ============================================
# ROUTE MODUL SALES (PREDIKSI JSON BIASA)
# ============================================

@app.route('/api/forecast/penjualan-harian', methods=['POST'])
def forecast_daily_route():
    req = request.get_json()
    store_id = req.get('m_store_id') if req else None
    
    if not store_id: return jsonify({"success": False, "message": "m_store_id wajib diisi.", "data": None}), 400
    hasil, err = sales_forecaster.predict_daily(store_id)
    return jsonify({"success": not err, "message": err or "Forecast Harian berhasil.", "data": hasil}), 404 if err else 200

@app.route('/api/forecast/penjualan-mingguan', methods=['POST'])
def forecast_weekly_route():
    req = request.get_json()
    store_id = req.get('m_store_id') if req else None
    
    if not store_id: return jsonify({"success": False, "message": "m_store_id wajib diisi.", "data": None}), 400
    hasil, err = sales_forecaster.predict_weekly(store_id)
    return jsonify({"success": not err, "message": err or "Forecast Mingguan berhasil.", "data": hasil}), 404 if err else 200

@app.route('/api/forecast/penjualan-bulanan', methods=['POST'])
def forecast_monthly_route():
    req = request.get_json()
    store_id = req.get('m_store_id') if req else None
    n_months = int(req.get('n_months', 1)) if req else 1
    
    if not store_id: return jsonify({"success": False, "message": "m_store_id wajib diisi.", "data": None}), 400
    hasil, err = sales_forecaster.predict_monthly(store_id, n_months)
    return jsonify({"success": not err, "message": err or "Forecast Bulanan berhasil.", "data": hasil}), 404 if err else 200

# ============================================
# ROUTE UNTUK MENYIMPAN LANGSUNG KE DATABASE
# ============================================

@app.route('/api/forecast/sales', methods=['POST'])
def save_forecast_route():
    req = request.get_json()
    store_id = req.get('m_store_id') or req.get('store_id')
    granularity = req.get('granularity', 'daily').lower()
    periods = int(req.get('periods', 1))
    
    if not store_id: return jsonify({"success": False, "message": "m_store_id wajib diisi."}), 400
        
    success, message = sales_forecaster.save_forecast_to_db(store_id, granularity=granularity, periods=periods)
    
    if success:
        return jsonify({"success": True, "message": message}), 200
    else:
        return jsonify({"success": False, "message": message}), 500

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