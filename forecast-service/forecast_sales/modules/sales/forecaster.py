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
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}")
            return []

    def load_models(self):
        try:
            self.daily_models = joblib.load(Config.DAILY_MODEL_PATH)
            print(f"[Forecaster] Berhasil memuat {len(self.daily_models)} model harian.")
        except FileNotFoundError:
            print("[Forecaster] Model harian belum tersedia. Jalankan trainer.")
            
        try:
            self.monthly_models = joblib.load(Config.MONTHLY_MODEL_PATH)
            print(f"[Forecaster] Berhasil memuat {len(self.monthly_models)} model bulanan.")
        except FileNotFoundError:
            print("[Forecaster] Model bulanan belum tersedia. Jalankan trainer.")

    # ==========================================
    # PREDIKSI HARIAN
    # ==========================================
    def predict_daily(self, store_id):
        if store_id not in self.daily_models:
            return None, "Model harian untuk toko ini tidak ditemukan."

        model_data = self.daily_models[store_id]
        rf_model = model_data["model"]
        fitur_x = model_data["fitur_x"]
        last_date = model_data["last_date"]

        future_dates = [last_date + timedelta(days=i) for i in range(1, 8)]
        future_df = pd.DataFrame({'date': future_dates})
        future_df['day_of_week'] = future_df['date'].dt.dayofweek
        future_df['month'] = future_df['date'].dt.month
        future_df['is_weekend'] = future_df['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
        future_df['total_discount'] = 0 
        
        X_future = future_df[fitur_x]
        all_tree_preds = np.array([tree.predict(X_future.values) for tree in rf_model.estimators_])
        mean_preds = all_tree_preds.mean(axis=0)
        std_preds = all_tree_preds.std(axis=0)

        nama_hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        hasil_akhir = []

        for i, date in enumerate(future_dates):
            pred_val, std_val = mean_preds[i], std_preds[i]
            batas_bawah = max(0, pred_val - (1.96 * std_val))
            batas_atas = pred_val + (1.96 * std_val)
            cv = (std_val / pred_val) if pred_val > 0 else 0
            conf_level = max(0.0, 100.0 - (cv * 100.0))

            hari_index = date.weekday()
            hasil_akhir.append({
                "tanggal": date.strftime('%Y-%m-%d'),
                "day_of_week": nama_hari[hari_index],
                "is_weekend": bool(hari_index >= 5),
                "forecast_omzet_total": int(pred_val),
                "estimated range": {"lower_bound": int(batas_bawah), "upper_bound": int(batas_atas)},
                "confidence level": f"{round(conf_level, 2)}%"
            })
        return hasil_akhir, None

    # ==========================================
    # PREDIKSI BULANAN
    # ==========================================
    def predict_monthly(self, store_id):
        if store_id not in self.monthly_models:
            return None, "Model bulanan untuk toko ini tidak ditemukan."

        model_data = self.monthly_models[store_id]
        rf_model = model_data["model"]
        fitur_x = model_data["fitur_x"]
        last_date = model_data["last_date"]

        future_dates = [last_date + pd.DateOffset(months=i) for i in range(1, 7)]
        future_df = pd.DataFrame({'date': future_dates})
        future_df['month'] = future_df['date'].dt.month
        future_df['quarter'] = future_df['date'].dt.quarter
        future_df['total_discount'] = 0 
        
        X_future = future_df[fitur_x]
        all_tree_preds = np.array([tree.predict(X_future.values) for tree in rf_model.estimators_])
        mean_preds = all_tree_preds.mean(axis=0)
        std_preds = all_tree_preds.std(axis=0)

        hasil_akhir = []
        for i, date in enumerate(future_dates):
            pred_val, std_val = mean_preds[i], std_preds[i]
            batas_bawah = max(0, pred_val - (1.96 * std_val))
            batas_atas = pred_val + (1.96 * std_val)
            cv = (std_val / pred_val) if pred_val > 0 else 0
            conf_level = max(0.0, 100.0 - (cv * 100.0))

            hasil_akhir.append({
                "bulan_tahun": date.strftime('%Y-%m'),
                "forecast_omzet_total": int(pred_val),
                "estimated range": {"lower_bound": int(batas_bawah), "upper_bound": int(batas_atas)},
                "confidence level": f"{round(conf_level, 2)}%"
            })
        return hasil_akhir, None