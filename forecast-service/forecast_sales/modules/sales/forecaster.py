import requests
import pandas as pd
import numpy as np
import joblib
from datetime import timedelta
from config import Config

class SalesForecaster:
    def __init__(self):
        self.daily_models = {}
        self.weekly_models = {}
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
        try: self.weekly_models = joblib.load(Config.WEEKLY_MODEL_PATH) # LOAD WEEKLY
        except: pass
        try: self.monthly_models = joblib.load(Config.MONTHLY_MODEL_PATH)
        except: pass

    def get_confidence(self, metrics):
        conf_score = max(0, min(99.9, 100 - metrics.get('mape', 20)))
        conf_str = "HIGH" if conf_score >= 70 else "MEDIUM" if conf_score >= 50 else "LOW"
        return round(conf_score, 2), conf_str

    # ==========================================
    # PREDIKSI HARIAN (7 HARI)
    # ==========================================
    def predict_daily(self, store_id):
        if store_id not in self.daily_models: return None, "Model harian tidak ditemukan."
        md = self.daily_models[store_id]
        rf, fx, last_date, met = md["model"], md["fitur_x"], md["last_date"], md.get("metrics", {})

        fd = [last_date + timedelta(days=i) for i in range(1, 8)]
        df = pd.DataFrame({'date': fd})
        df['day_of_week'] = df['date'].dt.dayofweek
        df['month'] = df['date'].dt.month
        df['is_weekend'] = df['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
        df['day_of_month'] = df['date'].dt.day
        df['is_payday'] = df['day_of_month'].apply(lambda x: 1 if (x >= 25 or x <= 5) else 0)
        df['total_discount'] = 0 
        
        preds = np.array([tree.predict(df[fx].values) for tree in rf.estimators_])
        m_preds, s_preds = preds.mean(axis=0), preds.std(axis=0)

        n_hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        res = []
        for i, d in enumerate(fd):
            p, s = m_preds[i], s_preds[i]
            cl = max(0.0, 100.0 - ((s/p)*100)) if p > 0 else 0
            idx = d.weekday()
            res.append({"date": d.strftime('%Y-%m-%d'), "day_of_week": n_hari[idx], "is_weekend": bool(idx>=5), "forecast_omzet_total": int(p), "estimated_range": {"lower_bound": int(max(0, p-(1.96*s))), "upper_bound": int(p+(1.96*s))}, "confidence_level": f"{round(cl, 2)}%"})

        tot = sum(x['forecast_omzet_total'] for x in res)
        h = max(res, key=lambda x: x['forecast_omzet_total'])
        trend = "UPWARD" if sum(x['forecast_omzet_total'] for x in res[3:])/4 > sum(x['forecast_omzet_total'] for x in res[:3])/3 else "DOWNWARD"
        sc, sl = self.get_confidence(met)

        return {"store_id": store_id, "metrics": met, "forecast_summary": {"total_predicted_omzet_next_7_days": int(tot), "average_daily_omzet": round(tot/7, 2)}, "prediction_analysis": {"highest_prediction_day": h['date'], "trend_direction": trend}, "model_confidence": {"confidence_score": sc, "confidence_level": sl}, "insights": [f"Prediksi cenderung {trend.lower()}.", f"Puncak pada {h['day_of_week']}."], "daily_forecast": res}, None

    # ==========================================
    # PREDIKSI MINGGUAN (4 MINGGU) - BARU!
    # ==========================================
    def predict_weekly(self, store_id):
        if store_id not in self.weekly_models: return None, "Model mingguan tidak ditemukan."
        md = self.weekly_models[store_id]
        rf, fx, last_date, met = md["model"], md["fitur_x"], md["last_date"], md.get("metrics", {})

        # Prediksi 4 minggu ke depan (Maju per 7 hari)
        fd = [last_date + timedelta(weeks=i) for i in range(1, 5)]
        df = pd.DataFrame({'date': fd})
        df['week_of_year'] = df['date'].dt.isocalendar().week
        df['month'] = df['date'].dt.month
        df['total_discount'] = 0 
        
        preds = np.array([tree.predict(df[fx].values) for tree in rf.estimators_])
        m_preds, s_preds = preds.mean(axis=0), preds.std(axis=0)

        res = []
        for i, d in enumerate(fd):
            p, s = m_preds[i], s_preds[i]
            cl = max(0.0, 100.0 - ((s/p)*100)) if p > 0 else 0
            res.append({"minggu_ke": i+1, "tanggal_awal_minggu": d.strftime('%Y-%m-%d'), "forecast_omzet_total": int(p), "estimated_range": {"lower_bound": int(max(0, p-(1.96*s))), "upper_bound": int(p+(1.96*s))}, "confidence_level": f"{round(cl, 2)}%"})

        tot = sum(x['forecast_omzet_total'] for x in res)
        h = max(res, key=lambda x: x['forecast_omzet_total'])
        trend = "UPWARD" if sum(x['forecast_omzet_total'] for x in res[2:])/2 > sum(x['forecast_omzet_total'] for x in res[:2])/2 else "DOWNWARD"
        sc, sl = self.get_confidence(met)

        return {"store_id": store_id, "metrics": met, "forecast_summary": {"total_predicted_omzet_next_4_weeks": int(tot), "average_weekly_omzet": round(tot/4, 2)}, "prediction_analysis": {"highest_prediction_week": h['minggu_ke'], "trend_direction": trend}, "model_confidence": {"confidence_score": sc, "confidence_level": sl}, "insights": [f"Prediksi 4 minggu ke depan cenderung {trend.lower()}.", f"Puncak omzet pada Minggu ke-{h['minggu_ke']}."], "weekly_forecast": res}, None

    # ==========================================
    # PREDIKSI BULANAN (6 BULAN)
    # ==========================================
    def predict_monthly(self, store_id):
        if store_id not in self.monthly_models: return None, "Model bulanan tidak ditemukan."
        md = self.monthly_models[store_id]
        rf, fx, last_date, met = md["model"], md["fitur_x"], md["last_date"], md.get("metrics", {})

        fd = [last_date + pd.DateOffset(months=i) for i in range(1, 7)]
        df = pd.DataFrame({'date': fd})
        df['month'] = df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        df['total_discount'] = 0 
        
        preds = np.array([tree.predict(df[fx].values) for tree in rf.estimators_])
        m_preds, s_preds = preds.mean(axis=0), preds.std(axis=0)

        res = []
        for i, d in enumerate(fd):
            p, s = m_preds[i], s_preds[i]
            cl = max(0.0, 100.0 - ((s/p)*100)) if p > 0 else 0
            res.append({"bulan_tahun": d.strftime('%Y-%m'), "forecast_omzet_total": int(p), "estimated_range": {"lower_bound": int(max(0, p-(1.96*s))), "upper_bound": int(p+(1.96*s))}, "confidence_level": f"{round(cl, 2)}%"})

        tot = sum(x['forecast_omzet_total'] for x in res)
        h = max(res, key=lambda x: x['forecast_omzet_total'])
        trend = "UPWARD" if sum(x['forecast_omzet_total'] for x in res[3:])/3 > sum(x['forecast_omzet_total'] for x in res[:3])/3 else "DOWNWARD"
        sc, sl = self.get_confidence(met)

        return {"store_id": store_id, "metrics": met, "forecast_summary": {"total_predicted_omzet_next_6_months": int(tot), "average_monthly_omzet": round(tot/6, 2)}, "prediction_analysis": {"highest_prediction_month": h['bulan_tahun'], "trend_direction": trend}, "model_confidence": {"confidence_score": sc, "confidence_level": sl}, "insights": [f"Prediksi 6 bulan cenderung {trend.lower()}."], "monthly_forecast": res}, None