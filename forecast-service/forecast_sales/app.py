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
    req = request.get_json()
    if not req or 'm_store_id' not in req: return jsonify({"success": False, "message": "m_store_id wajib diisi.", "data": None}), 400
    hasil, err = forecaster.predict_daily(req['m_store_id'])
    return jsonify({"success": not err, "message": err or "Forecast Harian berhasil.", "data": hasil}), 404 if err else 200

@app.route('/api/forecast/penjualan-mingguan', methods=['POST'])
def forecast_weekly_route():
    req = request.get_json()
    if not req or 'm_store_id' not in req: return jsonify({"success": False, "message": "m_store_id wajib diisi.", "data": None}), 400
    hasil, err = forecaster.predict_weekly(req['m_store_id'])
    return jsonify({"success": not err, "message": err or "Forecast Mingguan berhasil.", "data": hasil}), 404 if err else 200

@app.route('/api/forecast/penjualan-bulanan', methods=['POST'])
def forecast_monthly_route():
    req = request.get_json()
    if not req or 'm_store_id' not in req: return jsonify({"success": False, "message": "m_store_id wajib diisi.", "data": None}), 400
    hasil, err = forecaster.predict_monthly(req['m_store_id'])
    return jsonify({"success": not err, "message": err or "Forecast Bulanan berhasil.", "data": hasil}), 404 if err else 200

if __name__ == '__main__':
    app.run(port=int(os.getenv("FLASK_PORT", 5000)), debug=True)