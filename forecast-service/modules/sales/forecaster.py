import requests
import pandas as pd
import numpy as np
import joblib
import os
import json
from datetime import timedelta, datetime, timezone
from config import Config

class SalesForecaster:
    def __init__(self):
        self.global_model_data = None

    def fetch_data(self, endpoint):
        try:
            response = requests.get(f"{Config.BACKEND_API_URL}/{endpoint}")
            if response.status_code == 200: return response.json()
            return []
        except: return []

    def load_models(self):
        global_path = os.path.join(os.path.dirname(Config.DAILY_MODEL_PATH), 'models_rf_global.joblib')
        try: self.global_model_data = joblib.load(global_path)
        except: pass

    def get_confidence(self, metrics):
        conf_score = max(0, min(99.9, 100 - metrics.get('mape', 20)))
        conf_str = "HIGH" if conf_score >= 80 else "MEDIUM" if conf_score >= 60 else "LOW"
        return round(conf_score, 2), conf_str

    # ==========================================
    # ENGINE PREDIKSI BOTTOM-UP GLOBAL
    # ==========================================
    def _predict_days(self, store_id, days_to_predict):
        if not self.global_model_data: return None, "Model Global tidak ditemukan."
        md = self.global_model_data
        
        # Validasi toko
        try:
            store_encoded = md['label_encoder'].transform([store_id])[0]
        except ValueError:
            return None, "Toko tidak dikenali di dalam Model Global (Cold-Start gagal mapping)."
            
        # Ambil DNA Toko
        store_dna = md['store_stats'].get(store_id, {'store_mean': 0, 'store_std': 0, 'weekend_ratio': 1})
        last_date = md['last_dates'].get(store_id, pd.Timestamp.now())
        rf = md['model']
        fx = md['fitur_x']
        met = md['metrics']

        fd = [last_date + timedelta(days=i) for i in range(1, days_to_predict + 1)]
        df = pd.DataFrame({'date': fd})
        
        # Masukkan DNA Toko ke data masa depan
        df['store_id_encoded'] = store_encoded
        df['store_mean_omzet'] = store_dna['store_mean']
        df['store_std_omzet'] = store_dna['store_std']
        df['store_weekend_ratio'] = store_dna['weekend_ratio']
        
        # Masukkan Waktu Kalender
        df['day_of_week'] = df['date'].dt.dayofweek
        df['month'] = df['date'].dt.month
        df['day_of_month'] = df['date'].dt.day
        df['week_of_month'] = ((df['date'].dt.day - 1) // 7) + 1
        df['is_weekend'] = df['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
        df['is_payday'] = df['day_of_month'].apply(lambda x: 1 if (x >= 25 or x <= 5) else 0)
        df['total_discount'] = 0 
        
        preds = np.array([tree.predict(df[fx].values) for tree in rf.estimators_])
        m_preds, s_preds = preds.mean(axis=0), preds.std(axis=0)
        
        s_preds = np.clip(s_preds, 0, m_preds * 0.15)
        
        res = []
        for i, d in enumerate(fd):
            res.append({
                "date": d,
                "p": m_preds[i],
                "s": s_preds[i]
            })
            
        return res, met

    # ==========================================
    # PREDIKSI HARIAN (7 HARI)
    # ==========================================
    def predict_daily(self, store_id):
        raw_res, err = self._predict_days(store_id, 7)
        if err and not isinstance(err, dict): return None, err
        met = err

        n_hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        res = []
        for r in raw_res:
            p, s, d = r["p"], r["s"], r["date"]
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
        raw_res, err = self._predict_days(store_id, 28)
        if err and not isinstance(err, dict): return None, err
        met = err

        df = pd.DataFrame(raw_res)
        df['week_idx'] = np.arange(len(df)) // 7
        
        res = []
        for w, group in df.groupby('week_idx'):
            p_sum = group['p'].sum()
            s_sum = np.sqrt((group['s']**2).sum())
            start_date = group['date'].iloc[0]
            
            cl = max(0.0, 100.0 - ((s_sum/p_sum)*100)) if p_sum > 0 else 0
            label = f"Minggu ke-{w+1}"
            res.append({
                "period_identifier": start_date.strftime('%Y-%m-%d'), 
                "period_label": label, 
                "forecast_omzet_total": int(p_sum), 
                "estimated_range": {"lower_bound": int(max(0, p_sum-(1.96*s_sum))), "upper_bound": int(p_sum+(1.96*s_sum))}, 
                "confidence_level": f"{round(cl, 2)}%"
            })

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
    # PREDIKSI BULANAN
    # ==========================================
    def predict_monthly(self, store_id, n_months=1):
        raw_res, err = self._predict_days(store_id, n_months * 30) 
        if err and not isinstance(err, dict): return None, err
        met = err

        df = pd.DataFrame(raw_res)
        df['year_month'] = df['date'].dt.to_period('M')
        
        unique_months = df['year_month'].unique()[:n_months]
        
        n_bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
        res = []
        for m in unique_months:
            group = df[df['year_month'] == m]
            p_sum = group['p'].sum()
            s_sum = np.sqrt((group['s']**2).sum())
            
            cl = max(0.0, 100.0 - ((s_sum/p_sum)*100)) if p_sum > 0 else 0
            label = f"{n_bulan[m.month-1]} {m.year}"
            res.append({
                # FIX DI SINI: Mengubah '2020-07' menjadi format lengkap '2020-07-01'
                "period_identifier": m.start_time.strftime('%Y-%m-%d'), 
                "period_label": label, 
                "forecast_omzet_total": int(p_sum), 
                "estimated_range": {"lower_bound": int(max(0, p_sum-(1.96*s_sum))), "upper_bound": int(p_sum+(1.96*s_sum))}, 
                "confidence_level": f"{round(cl, 2)}%"
            })

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
    # ==========================================
    # SAVE TO DATABASE (GOLANG API)
    # ==========================================
    def save_forecast_to_db(self, store_id, granularity='daily', periods=1):
        if granularity == 'daily':
            result, err = self.predict_daily(store_id)
            horizon_label = 'daily'
            horizon_days = 7
        elif granularity == 'weekly':
            result, err = self.predict_weekly(store_id)
            horizon_label = 'weekly'
            horizon_days = 28
        elif granularity == 'monthly':
            result, err = self.predict_monthly(store_id, n_months=periods)
            horizon_label = 'monthly'
            horizon_days = periods * 30
        else:
            return False, "Granularity harus 'daily', 'weekly', atau 'monthly'"

        if err and not isinstance(err, dict): return False, err

        metrics = result.get('metrics', {})
        summary = result.get('forecast_summary', {})
        forecast_array = result.get('forecast_data', [])
        
        if not forecast_array:
            return False, "Array forecast kosong, prediksi gagal."

        model_version = "1.0.0"

        # 1. Siapkan & Kirim ke forecast_predictions (Dashboard Cepat)
        pred_rows = []
        for item in forecast_array:
            pred_rows.append({
                "store_id": store_id,
                "module": "sales",
                "horizon_label": horizon_label,
                "horizon_days": horizon_days,
                "prediction_date": item['period_identifier'],
                "predicted_value": float(item.get('forecast_omzet_total', 0)),
                "lower_bound": float(item.get('estimated_range', {}).get('lower_bound', 0)),
                "upper_bound": float(item.get('estimated_range', {}).get('upper_bound', 0)),
                "mae": metrics.get('mae', 0.0),
                "rmse": metrics.get('rmse', 0.0),
                "mape": metrics.get('mape', 0.0),
                "model_version": model_version,
            })

        try:
            resp_pred = requests.post(f"{Config.BACKEND_API_URL}/forecast-predictions", json={"predictions": pred_rows})
            resp_pred.raise_for_status()
            print(f"[SAVED] {len(forecast_array)} baris ke forecast_predictions")
        except Exception as e:
            err_text = getattr(e.response, 'text', str(e)) if hasattr(e, 'response') and e.response else str(e)
            print(f"[ERROR] Gagal simpan forecast_predictions: {err_text}")
            return False, f"Gagal simpan forecast_predictions: {err_text}"

        # 2. Siapkan & Kirim ke forecast_runs (Tabel Header/Induk)
        now = datetime.now(timezone.utc).isoformat()
        
        md = self.global_model_data
        train_end = "2024-12-31" 
        if md and 'last_dates' in md and store_id in md['last_dates']:
            train_end = md['last_dates'][store_id].strftime('%Y-%m-%d')

        run_payload = {
            "store_id": store_id,
            "forecast_type": "sales",
            "horizon_label": horizon_label,
            "horizon_days": horizon_days,
            "granularity": granularity,
            "model_name": "random forest global",
            "model_version": model_version,
            "feature_version": "v1",
            "train_start_date": "2020-01-01",
            "train_end_date": train_end,
            "predict_start_date": forecast_array[0]['period_identifier'],
            "predict_end_date": forecast_array[-1]['period_identifier'],
            "metrics": json.dumps(metrics),
            "summary": json.dumps(summary),
            "data_quality": json.dumps({"date_range": {"start": "2020-01-01", "end": train_end}}),
            "status": "success",
            "started_at": now,
            "finished_at": now
        }

        run_id = None
        try:
            resp = requests.post(f"{Config.BACKEND_API_URL}/forecast-runs", json=run_payload)
            resp.raise_for_status()
            run_data = resp.json()
            run_id = run_data.get('run_id') or run_data.get('data', {}).get('id')
            if not run_id: return False, "Berhasil insert forecast_runs tapi run_id tidak kembali."
            print(f"[SAVED] forecast_runs run_id={run_id}")
        except Exception as e:
            return False, f"Gagal simpan forecast_runs: {e}"

        # 3. Siapkan & Kirim ke forecast_results (Tabel Detail Harian/Mingguan/Bulanan)
        results_data = []
        conf_score = result.get('model_confidence', {}).get('confidence_score', 0)
        
        for item in forecast_array:
            results_data.append({
                "target_date": item['period_identifier'],
                "predicted_value": float(item.get('forecast_omzet_total', 0)),
                "lower_bound": float(item.get('estimated_range', {}).get('lower_bound', 0)),
                "upper_bound": float(item.get('estimated_range', {}).get('upper_bound', 0)),
                "confidence_level": int(round(conf_score)),
                "item_id": None, 
                "item_type": "sales"
            })

        try:
            resp = requests.post(f"{Config.BACKEND_API_URL}/forecast-results", json={"run_id": run_id, "results": results_data})
            resp.raise_for_status()
            print(f"[SAVED] {len(forecast_array)} baris ke forecast_results untuk run_id={run_id}")
        except Exception as e:
            return False, f"Gagal simpan forecast_results: {e}"

        return True, f"Semua data forecast {granularity} berhasil disimpan ke database!"