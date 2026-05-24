import os
from flask import Flask, jsonify, request
from config import Config
from modules.sales.forecaster import SalesForecaster

app = Flask(__name__)

Config.init_app()
forecaster = SalesForecaster()
forecaster.load_models()

@app.route('/api/forecast/penjualan-harian', methods=['POST'])
def forecast_daily_route():
    req_data = request.get_json()
    if not req_data or 'm_store_id' not in req_data:
        return jsonify({"success": False, "message": "Parameter 'm_store_id' wajib diisi.", "data": None}), 400

    hasil, error = forecaster.predict_daily(req_data['m_store_id'])
    if error: return jsonify({"success": False, "message": error, "data": None}), 404
    return jsonify({"success": True, "message": "Forecast Harian berhasil.", "data": hasil})

@app.route('/api/forecast/penjualan-bulanan', methods=['POST'])
def forecast_monthly_route():
    req_data = request.get_json()
    if not req_data or 'm_store_id' not in req_data:
        return jsonify({"success": False, "message": "Parameter 'm_store_id' wajib diisi.", "data": None}), 400

    hasil, error = forecaster.predict_monthly(req_data['m_store_id'])
    if error: return jsonify({"success": False, "message": error, "data": None}), 404
    return jsonify({"success": True, "message": "Forecast Bulanan berhasil.", "data": hasil})

if __name__ == '__main__':
    port = int(os.getenv("FLASK_PORT", 5000))
    app.run(port=port, debug=True)