from flask import Flask, request, jsonify
import traceback
import uuid
import threading

# Import modul inventory (punya kamu)
from modules.inventory.forecaster import InventoryForecaster
from modules.inventory.trainer import train_all_inventory_models, training_tasks

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
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ============================================
# ROUTE MODUL LAIN (VISITOR, SALES, dll.)
# ============================================



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
        "freq": "W"   // "W" atau "M"
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
        if freq not in ['W', 'M']:
            return jsonify({"error": "freq harus 'W' (mingguan) atau 'M' (bulanan)"}), 400

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)