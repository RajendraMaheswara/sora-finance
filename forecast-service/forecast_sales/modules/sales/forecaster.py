import requests
import pandas as pd
import numpy as np
import joblib
from datetime import timedelta
from config import Config

class SalesForecaster:
    def __init__(self):
        self.daily_models = {}
        self.monthly_models = {}

    def fetch_data(self, endpoint):
        try:
            response = requests.get(f"{Config.BACKEND_API_URL}/{endpoint}")
            if response.status_code == 200: return response.json()
            return []
        except: return []

    def load_models(self):
        try: self.daily_models = joblib.load(Config.DAILY_MODEL_PATH)
        except: pass
        try: self.monthly_models = joblib.load(Config.MONTHLY_MODEL_PATH)
        except: pass

    # ==========================================
    # PREDIKSI HARIAN (7 HARI)
    # ==========================================
    def predict_daily(self, store_id):
        if store_id not in self.daily_models:
            return None, "Model harian untuk toko ini tidak ditemukan."

        model_data = self.daily_models[store_id]
        rf_model, fitur_x, last_date, metrics = model_data["model"], model_data["fitur_x"], model_data["last_date"], model_data.get("metrics", {})

        future_dates = [last_date + timedelta(days=i) for i in range(1, 8)]
        future_df = pd.DataFrame({'date': future_dates})
        future_df['day_of_week'] = future_df['date'].dt.dayofweek
        future_df['month'] = future_df['date'].dt.month
        future_df['is_weekend'] = future_df['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
        future_df['total_discount'] = 0 
        future_df['day_of_month'] = future_df['date'].dt.day
        future_df['is_payday'] = future_df['day_of_month'].apply(lambda x: 1 if (x >= 25 or x <= 5) else 0)
        all_tree_preds = np.array([tree.predict(future_df[fitur_x].values) for tree in rf_model.estimators_])
        mean_preds = all_tree_preds.mean(axis=0)
        std_preds = all_tree_preds.std(axis=0)

        nama_hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        daily_forecast = []

        for i, date in enumerate(future_dates):
            pred_val, std_val = mean_preds[i], std_preds[i]
            conf_level = max(0.0, 100.0 - ((std_val / pred_val) * 100.0)) if pred_val > 0 else 0
            hari_index = date.weekday()

            daily_forecast.append({
                "date": date.strftime('%Y-%m-%d'),
                "day_of_week": nama_hari[hari_index],
                "is_weekend": bool(hari_index >= 5),
                "forecast_omzet_total": int(pred_val),
                "estimated_range": {"lower_bound": int(max(0, pred_val - (1.96 * std_val))), "upper_bound": int(pred_val + (1.96 * std_val))},
                "confidence_level": f"{round(conf_level, 2)}%"
            })

        total_7 = sum(x['forecast_omzet_total'] for x in daily_forecast)
        highest_day = max(daily_forecast, key=lambda x: x['forecast_omzet_total'])
        lowest_day = min(daily_forecast, key=lambda x: x['forecast_omzet_total'])
        
        avg_first_half = sum(x['forecast_omzet_total'] for x in daily_forecast[:3]) / 3
        avg_second_half = sum(x['forecast_omzet_total'] for x in daily_forecast[3:]) / 4
        trend = "UPWARD" if avg_second_half > avg_first_half else "DOWNWARD"

        conf_score = max(0, min(99.9, 100 - metrics.get('mape', 20)))
        conf_level_str = "HIGH" if conf_score >= 80 else "MEDIUM" if conf_score >= 60 else "LOW"

        response_data = {
            "store_id": store_id,
            "metrics": metrics,
            "forecast_summary": {"total_predicted_omzet_next_7_days": int(total_7), "average_daily_omzet": round(total_7 / 7, 2)},
            "prediction_analysis": {"highest_prediction_day": highest_day['date'], "lowest_prediction_day": lowest_day['date'], "trend_direction": trend},
            "model_confidence": {"confidence_score": round(conf_score, 2), "confidence_level": conf_level_str},
            "insights": [
                f"Prediksi omzet 7 hari ke depan cenderung {'naik' if trend == 'UPWARD' else 'menurun'}.",
                f"Hari tertinggi pada {highest_day['day_of_week']} ({highest_day['forecast_omzet_total']})."
            ],
            "daily_forecast": daily_forecast
        }
        return response_data, None

    # ==========================================
    # PREDIKSI BULANAN (6 BULAN)
    # ==========================================
    def predict_monthly(self, store_id):
        if store_id not in self.monthly_models:
            return None, "Model bulanan untuk toko ini tidak ditemukan."

        model_data = self.monthly_models[store_id]
        rf_model, fitur_x, last_date, metrics = model_data["model"], model_data["fitur_x"], model_data["last_date"], model_data.get("metrics", {})

        future_dates = [last_date + pd.DateOffset(months=i) for i in range(1, 7)]
        future_df = pd.DataFrame({'date': future_dates})
        future_df['month'] = future_df['date'].dt.month
        future_df['quarter'] = future_df['date'].dt.quarter
        future_df['total_discount'] = 0 
        
        all_tree_preds = np.array([tree.predict(future_df[fitur_x].values) for tree in rf_model.estimators_])
        mean_preds = all_tree_preds.mean(axis=0)
        std_preds = all_tree_preds.std(axis=0)

        monthly_forecast = []
        for i, date in enumerate(future_dates):
            pred_val, std_val = mean_preds[i], std_preds[i]
            conf_level = max(0.0, 100.0 - ((std_val / pred_val) * 100.0)) if pred_val > 0 else 0
            
            monthly_forecast.append({
                "bulan_tahun": date.strftime('%Y-%m'),
                "forecast_omzet_total": int(pred_val),
                "estimated_range": {"lower_bound": int(max(0, pred_val - (1.96 * std_val))), "upper_bound": int(pred_val + (1.96 * std_val))},
                "confidence_level": f"{round(conf_level, 2)}%"
            })

        total_6 = sum(x['forecast_omzet_total'] for x in monthly_forecast)
        highest_month = max(monthly_forecast, key=lambda x: x['forecast_omzet_total'])
        lowest_month = min(monthly_forecast, key=lambda x: x['forecast_omzet_total'])

        avg_first_half = sum(x['forecast_omzet_total'] for x in monthly_forecast[:3]) / 3
        avg_second_half = sum(x['forecast_omzet_total'] for x in monthly_forecast[3:]) / 3
        trend = "UPWARD" if avg_second_half > avg_first_half else "DOWNWARD"

        conf_score = max(0, min(99.9, 100 - metrics.get('mape', 20)))
        conf_level_str = "HIGH" if conf_score >= 80 else "MEDIUM" if conf_score >= 60 else "LOW"

        response_data = {
            "store_id": store_id,
            "metrics": metrics,
            "forecast_summary": {"total_predicted_omzet_next_6_months": int(total_6), "average_monthly_omzet": round(total_6 / 6, 2)},
            "prediction_analysis": {"highest_prediction_month": highest_month['bulan_tahun'], "lowest_prediction_month": lowest_month['bulan_tahun'], "trend_direction": trend},
            "model_confidence": {"confidence_score": round(conf_score, 2), "confidence_level": conf_level_str},
            "insights": [f"Prediksi omzet 6 bulan ke depan cenderung {'naik' if trend == 'UPWARD' else 'menurun'}."],
            "monthly_forecast": monthly_forecast
        }
        return response_data, None