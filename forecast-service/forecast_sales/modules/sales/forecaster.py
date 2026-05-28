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
        try: self.weekly_models = joblib.load(Config.WEEKLY_MODEL_PATH)
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
            res.append({
                "period_identifier": d.strftime('%Y-%m-%d'), 
                "period_label": n_hari[idx], 
                "forecast_omzet_total": int(p), 
                "estimated_range": {"lower_bound": int(max(0, p-(1.96*s))), "upper_bound": int(p+(1.96*s))}, 
                "confidence_level": f"{round(cl, 2)}%"
            })

        tot = sum(x['forecast_omzet_total'] for x in res)
        h = max(res, key=lambda x: x['forecast_omzet_total'])
        trend = "UPWARD" if sum(x['forecast_omzet_total'] for x in res[3:])/4 > sum(x['forecast_omzet_total'] for x in res[:3])/3 else "DOWNWARD"
        sc, sl = self.get_confidence(met)

        return {
            "store_id": store_id, 
            "metrics": met, 
            "forecast_summary": {
                "total_predicted_omzet": int(tot), 
                "average_omzet": round(tot/7, 2),
                "period_count": 7,
                "period_type": "day"
            }, 
            "prediction_analysis": {
                "highest_prediction_period": h['period_label'], 
                "trend_direction": trend
            }, 
            "model_confidence": {
                "confidence_score": sc, 
                "confidence_level": sl
            }, 
            "insights": [f"Prediksi 7 hari ke depan cenderung {trend.lower()}.", f"Puncak omzet pada {h['period_label']}."], 
            "forecast_data": res
        }, None

    # ==========================================
    # PREDIKSI MINGGUAN (4 MINGGU)
    # ==========================================
    def predict_weekly(self, store_id):
        if store_id not in self.weekly_models: return None, "Model mingguan tidak ditemukan."
        md = self.weekly_models[store_id]
        rf, fx, last_date, met = md["model"], md["fitur_x"], md["last_date"], md.get("metrics", {})
        last_omzet = md.get("last_omzet", 0)
        last_4_omzet = md.get("last_4_omzet", [last_omzet]*4)

        fd = [last_date + timedelta(weeks=i) for i in range(1, 5)]
        current_lag_1 = last_omzet
        history_omzet = last_4_omzet.copy()
        
        res = []
        for i, d in enumerate(fd):
            current_lag_4 = history_omzet[-4]
            row = {
                'week_of_year': d.isocalendar().week,
                'month': d.month,
                'week_of_month': ((d.day - 1) // 7) + 1,
                'total_discount': 0,
                'lag_1': current_lag_1,
                'lag_4': current_lag_4
            }
            input_df = pd.DataFrame([row])[fx]
            
            preds = np.array([tree.predict(input_df.values) for tree in rf.estimators_])
            p, s = preds.mean(), preds.std()
            s = min(s, p * 0.15) 
            
            cl = max(0.0, 100.0 - ((s/p)*100)) if p > 0 else 0
            label = f"Minggu ke-{i+1}"
            res.append({
                "period_identifier": d.strftime('%Y-%m-%d'), 
                "period_label": label, 
                "forecast_omzet_total": int(p), 
                "estimated_range": {"lower_bound": int(max(0, p-(1.96*s))), "upper_bound": int(p+(1.96*s))}, 
                "confidence_level": f"{round(cl, 2)}%"
            })
            current_lag_1 = p
            history_omzet.append(p)

        tot = sum(x['forecast_omzet_total'] for x in res)
        h = max(res, key=lambda x: x['forecast_omzet_total'])
        trend = "UPWARD" if sum(x['forecast_omzet_total'] for x in res[2:])/2 > sum(x['forecast_omzet_total'] for x in res[:2])/2 else "DOWNWARD"
        sc, sl = self.get_confidence(met)

        return {
            "store_id": store_id, 
            "metrics": met, 
            "forecast_summary": {
                "total_predicted_omzet": int(tot), 
                "average_omzet": round(tot/4, 2),
                "period_count": 4,
                "period_type": "week"
            }, 
            "prediction_analysis": {
                "highest_prediction_period": h['period_label'], 
                "trend_direction": trend
            }, 
            "model_confidence": {
                "confidence_score": sc, 
                "confidence_level": sl
            }, 
            "insights": [f"Prediksi 4 minggu ke depan cenderung {trend.lower()}.", f"Puncak omzet pada {h['period_label']}."], 
            "forecast_data": res
        }, None

    # ==========================================
    # PREDIKSI BULANAN (1 BULAN)
    # ==========================================
    def predict_monthly(self, store_id, n_months=1):
        if store_id not in self.monthly_models: return None, "Model bulanan tidak ditemukan."
        md = self.monthly_models[store_id]
        rf, fx, last_date, met = md["model"], md["fitur_x"], md["last_date"], md.get("metrics", {})
        last_omzet = md.get("last_omzet", 0)

        fd = [last_date + pd.DateOffset(months=i) for i in range(1, n_months + 1)]
        current_lag_1 = last_omzet
        
        n_bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
        res = []
        for i, d in enumerate(fd):
            row = {
                'month': d.month,
                'quarter': d.quarter,
                'total_discount': 0,
                'lag_1': current_lag_1
            }
            input_df = pd.DataFrame([row])[fx]
            
            preds = np.array([tree.predict(input_df.values) for tree in rf.estimators_])
            p, s = preds.mean(), preds.std()
            s = min(s, p * 0.15) 
            
            cl = max(0.0, 100.0 - ((s/p)*100)) if p > 0 else 0
            label = f"{n_bulan[d.month-1]} {d.year}"
            res.append({
                "period_identifier": d.strftime('%Y-%m'), 
                "period_label": label, 
                "forecast_omzet_total": int(p), 
                "estimated_range": {"lower_bound": int(max(0, p-(1.96*s))), "upper_bound": int(p+(1.96*s))}, 
                "confidence_level": f"{round(cl, 2)}%"
            })
            current_lag_1 = p

        tot = sum(x['forecast_omzet_total'] for x in res)
        h = max(res, key=lambda x: x['forecast_omzet_total'])
        trend = "UPWARD" if len(res) > 1 and sum(x['forecast_omzet_total'] for x in res[len(res)//2:])/max(1, len(res)//2) > sum(x['forecast_omzet_total'] for x in res[:len(res)//2])/max(1, len(res)//2) else "STABIL" if len(res) == 1 else "DOWNWARD"
        sc, sl = self.get_confidence(met)

        return {
            "store_id": store_id, 
            "metrics": met, 
            "forecast_summary": {
                "total_predicted_omzet": int(tot), 
                "average_omzet": round(tot/n_months, 2),
                "period_count": n_months,
                "period_type": "month"
            }, 
            "prediction_analysis": {
                "highest_prediction_period": h['period_label'], 
                "trend_direction": trend
            }, 
            "model_confidence": {
                "confidence_score": sc, 
                "confidence_level": sl
            }, 
            "insights": [f"Prediksi {n_months} bulan ke depan.", f"Puncak omzet pada {h['period_label']}."], 
            "forecast_data": res
        }, None