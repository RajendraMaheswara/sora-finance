from flask import Flask, request, jsonify
from modules.inventory.forecaster import InventoryForecaster
from modules.inventory.trainer import train_all_inventory_models
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import traceback

app = Flask(__name__)

# ============================================
# SCHEDULER: Retrain otomatis tiap Minggu 02:00
# ============================================
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=train_all_inventory_models,
    trigger="cron",
    day_of_week="sun",
    hour=2,
    minute=0
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ============================================
# ROUTE 
# ============================================




# ============================================
# ROUTE INVENTORY (STOK BARANG)
# ============================================
@app.route('/api/inventory/forecast', methods=['POST'])
def forecast_inventory():
    """
    Dipanggil oleh backend Go untuk mendapatkan forecast stok bahan baku.
    Request JSON:
    {
        "store_id": "...",
        "ingredient_id": "...",
        "periods": 4,        // jumlah minggu/bulan ke depan
        "freq": "W"          // "W" untuk mingguan, "M" untuk bulanan
    }
    """
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        ingredient_id = data.get('ingredient_id')
        periods = int(data.get('periods', 1))
        freq = data.get('freq', 'W').upper()

        # Validasi
        if not store_id or not ingredient_id:
            return jsonify({"error": "store_id dan ingredient_id wajib diisi"}), 400
        if freq not in ['W', 'M']:
            return jsonify({"error": "freq harus 'W' (mingguan) atau 'M' (bulanan)"}), 400

        # Jalankan forecasting
        forecaster = InventoryForecaster(store_id, ingredient_id)
        hasil = forecaster.predict(periods=periods, freq=freq)

        # Ubah DataFrame hasil ke list of dict
        hasil_json = hasil.to_dict(orient='records')

        return jsonify({
            "status": "sukses",
            "pesan": f"Forecast {freq} untuk {periods} periode ke depan",
            "data": hasil_json
        })

    except FileNotFoundError:
        # Model belum ada
        return jsonify({
            "error": "Model belum di-training. Silakan panggil endpoint /api/inventory/train terlebih dahulu."
        }), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ============================================
# ROUTE UNTUK TRAINING MANUAL (ADMIN)
# ============================================
@app.route('/api/inventory/train', methods=['POST'])
def train_inventory():
    """
    Memulai training semua model inventory.
    Bisa dipanggil manual oleh admin atau dijadwalkan.
    """
    try:
        train_all_inventory_models()
        return jsonify({"status": "sukses", "pesan": "Training selesai"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)