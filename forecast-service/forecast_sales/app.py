import os
from flask import Flask, jsonify, request
from config import Config
from modules.sales.forecaster import SalesForecaster

app = Flask(__name__)

# 1. Inisialisasi folder dan muat model ke memori
Config.init_app()
forecaster = SalesForecaster()
forecaster.load_models()

# 2. Rute Forecasting Harian
@app.route('/api/forecast/penjualan-harian', methods=['POST'])
def forecast_daily_route():
    req_data = request.get_json()
    if not req_data or 'm_store_id' not in req_data:
        return jsonify({"status": "error", "pesan": "Parameter 'm_store_id' wajib diisi."}), 400

    store_id = req_data['m_store_id']
    hasil, error = forecaster.predict_daily(store_id)
    
    if error:
        return jsonify({"status": "error", "pesan": error}), 404

    return jsonify({"status": "sukses", "tipe": "Harian (7 Hari)", "data_forecast": hasil})

# 3. Rute Forecasting Bulanan
@app.route('/api/forecast/penjualan-bulanan', methods=['POST'])
def forecast_monthly_route():
    req_data = request.get_json()
    if not req_data or 'm_store_id' not in req_data:
        return jsonify({"status": "error", "pesan": "Parameter 'm_store_id' wajib diisi."}), 400

    store_id = req_data['m_store_id']
    hasil, error = forecaster.predict_monthly(store_id)
    
    if error:
        return jsonify({"status": "error", "pesan": error}), 404

    return jsonify({"status": "sukses", "tipe": "Bulanan (6 Bulan)", "data_forecast": hasil})

if __name__ == '__main__':
    port = int(os.getenv("FLASK_PORT", 5000))
    app.run(port=port, debug=True)