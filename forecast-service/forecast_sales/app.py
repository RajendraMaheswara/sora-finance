import os
import uuid
import threading
import traceback
from flask import Flask, jsonify, request
from config import Config

# Import modul Sales
from modules.sales.forecaster import SalesForecaster
from modules.sales.trainer import train_all as train_all_sales

app = Flask(__name__)

Config.init_app()

# Dictionary untuk tracking status training
sales_training_tasks = {}

forecaster = SalesForecaster()
forecaster.load_models()

# ============================================
# BACKGROUND TASK: FUNGSI TRAINING
# ============================================
def background_sales_training(task_id):
    try:
        sales_training_tasks[task_id]["status"] = "TRAINING"
        sales_training_tasks[task_id]["message"] = "Proses training Global Model Sales sedang berjalan..."
        
        train_all_sales()
        forecaster.load_models()
        
        sales_training_tasks[task_id]["status"] = "COMPLETED"
        sales_training_tasks[task_id]["message"] = "Training Global Model Sales selesai."
    except Exception as e:
        traceback.print_exc()
        sales_training_tasks[task_id]["status"] = "ERROR"
        sales_training_tasks[task_id]["message"] = str(e)


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
    hasil, err = forecaster.predict_daily(store_id)
    return jsonify({"success": not err, "message": err or "Forecast Harian berhasil.", "data": hasil}), 404 if err else 200

@app.route('/api/forecast/penjualan-mingguan', methods=['POST'])
def forecast_weekly_route():
    req = request.get_json()
    store_id = req.get('m_store_id') if req else None
    
    if not store_id: return jsonify({"success": False, "message": "m_store_id wajib diisi.", "data": None}), 400
    hasil, err = forecaster.predict_weekly(store_id)
    return jsonify({"success": not err, "message": err or "Forecast Mingguan berhasil.", "data": hasil}), 404 if err else 200

@app.route('/api/forecast/penjualan-bulanan', methods=['POST'])
def forecast_monthly_route():
    req = request.get_json()
    store_id = req.get('m_store_id') if req else None
    n_months = int(req.get('n_months', 1)) if req else 1
    
    if not store_id: return jsonify({"success": False, "message": "m_store_id wajib diisi.", "data": None}), 400
    hasil, err = forecaster.predict_monthly(store_id, n_months)
    return jsonify({"success": not err, "message": err or "Forecast Bulanan berhasil.", "data": hasil}), 404 if err else 200

# ============================================
# ROUTE UNTUK MENYIMPAN LANGSUNG KE DATABASE
# ============================================

@app.route('/api/forecast/save-to-db', methods=['POST'])
def save_forecast_route():
    req = request.get_json()
    store_id = req.get('m_store_id') or req.get('store_id')
    granularity = req.get('granularity', 'daily').lower()
    periods = int(req.get('periods', 1))
    
    if not store_id: return jsonify({"success": False, "message": "m_store_id wajib diisi."}), 400
        
    success, message = forecaster.save_forecast_to_db(store_id, granularity=granularity, periods=periods)
    
    if success:
        return jsonify({"success": True, "message": message}), 200
    else:
        return jsonify({"success": False, "message": message}), 500


if __name__ == '__main__':
    app.run(port=int(os.getenv("FLASK_PORT", 5000)), debug=True)