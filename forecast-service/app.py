from flask import Flask, request, jsonify
from config import Config
import os
import traceback
import uuid
import threading
import sys
import asyncio
from datetime import datetime, date

from modules.visitors.app.services.forecast_service import forecast_service as visitors_forecast_service
from modules.visitors.app.training.trainer import trainer as visitors_trainer
from modules.visitors.app.services.golang_client import golang_client

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

scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ============================================
# ROUTE MODUL LAIN (VISITOR, SALES, dll.)
# ============================================

# ============================================
# ROUTE MODUL VISITORS
# ============================================

@app.route('/api/forecast/visitors/predict', methods=['POST'])
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

@app.route('/api/forecast/visitors/models', methods=['GET'])
def visitors_list_models():
    stores = visitors_trainer.list_trained_stores()
    return jsonify({
        "status": "success",
        "trained_store_count": len(stores),
        "store_ids": stores,
    }), 200

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