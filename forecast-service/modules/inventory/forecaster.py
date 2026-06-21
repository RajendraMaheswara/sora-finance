"""Inventory forecasting for ingredients using Prophet."""

import itertools
import json
import os

import holidays
import joblib
import numpy as np
import pandas as pd
import requests
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics

from config import Config
from datetime import datetime, timezone

class InventoryForecaster:
    def __init__(self, store_id, ingredient_id, model_dir=None):
        if model_dir is None:
            model_dir = Config.MODEL_DIR

        self.store_id      = store_id
        self.ingredient_id = ingredient_id
        self.model_name    = f"model_store{store_id}_ingr{ingredient_id}"
        self.model_path    = os.path.join(model_dir, 'inventory', f"{self.model_name}.pkl")
        self.metrics_path  = os.path.join(model_dir, 'inventory', f"metrics_{self.model_name}.json")
        self.model         = None
        self.id_holidays   = holidays.ID()  # Kalender libur Indonesia

    # =========================================================================
    # DATA RETRIEVAL
    # =========================================================================

    def _get_historical_data(self, start_date='2020-01-01', end_date=None):
        """
        Ambil data dari API Go, lalu agregasi harian dengan SUM(reduced).

        Args:
            start_date (str): Batas bawah data (default '2020-01-01').
            end_date (str | None): Batas atas data. Jika None, akan diisi
                                    dengan tanggal hari ini (dinamis).
        """
        # Jika end_date tidak diberikan, gunakan tanggal hari ini
        if end_date is None:
            end_date = pd.Timestamp.now().strftime('%Y-%m-%d')

        url = f"{Config.BACKEND_API_URL}/ingredient-stock-histories"
        try:
            resp = requests.get(url, headers=Config.backend_headers(), timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Gagal mengambil data dari API: {e}")

        data    = resp.json()
        records = data['data'] if isinstance(data, dict) and 'data' in data else data

        if not records:
            raise ValueError("Data kosong dari API")

        df = pd.DataFrame(records)
        df = df[
            (df['m_store_id'] == self.store_id) &
            (df['m_food_ingredient_id'] == self.ingredient_id)
        ]
        if df.empty:
            raise ValueError(f"Tidak ada data untuk pasangan {self.store_id}-{self.ingredient_id}")

        df['date'] = pd.to_datetime(df['date'])
        df['date'] = df['date'].dt.tz_localize(None)
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        df = df[df['reduced'] > 0]

        if df.empty:
            raise ValueError(f"Tidak ada data pemakaian pada rentang {start_date} - {end_date}")

        # Agregasi harian
        daily = df.groupby(df['date'].dt.date)['reduced'].sum().reset_index()
        daily.columns = ['ds', 'y']
        daily['ds'] = pd.to_datetime(daily['ds'])

        # Hanya isi nol untuk rentang dari transaksi pertama hingga terakhir aktual
        max_actual_date = daily['ds'].max()
        full_range = pd.date_range(start=daily['ds'].min(), end=max_actual_date, freq='D')
        df_final   = pd.DataFrame({'ds': full_range}).merge(daily, on='ds', how='left')
        df_final['y'] = df_final['y'].fillna(0)

        return df_final[['ds', 'y']]

    # =========================================================================
    # FEATURE ENGINEERING
    # =========================================================================

    def _add_regressors(self, df):
        """
        Tambahkan fitur tambahan (regressors) ke dataframe.

        - is_weekend         : 1 jika Sabtu/Minggu
        - is_national_holiday: 1 jika hari libur nasional Indonesia
        - is_store_closed    : placeholder (default 0)
                               TODO: isi dari API kalender toko Go jika tersedia
        """
        df = df.copy()
        df['is_weekend']          = df['ds'].dt.dayofweek.isin([5, 6]).astype(int)
        df['is_national_holiday'] = df['ds'].apply(lambda x: 1 if x in self.id_holidays else 0)
        df['is_store_closed']     = 0
        return df

    # =========================================================================
    # ADAPTIVE TRAINING CONFIG
    # =========================================================================

    @staticmethod
    def _get_training_config(data_days: int) -> dict:
        """
        Tentukan parameter training berdasarkan panjang data yang tersedia.

        Tier:
          SHORT  : 90–364 hari  → cross-val konservatif, tanpa yearly seasonality, grid kecil
          MEDIUM : 365–729 hari → cross-val standar, yearly seasonality aktif, grid medium
          LONG   : 730+ hari    → full cross-val, semua fitur aktif, grid penuh
        """
        # [EDIT_POINT] Ubah threshold tier training di sini (SHORT/MEDIUM/LONG).
        if data_days >= 730:
            return {
                'yearly_seasonality': True,
                'cv_initial': '365 days',
                'cv_period':  '30 days',
                'cv_horizon': '30 days',
                # [EDIT_POINT] Ubah kombinasi hyperparameter LONG di sini.
                'param_grid': {
                    'changepoint_prior_scale': [0.01, 0.05, 0.1],
                    'seasonality_prior_scale': [1.0, 5.0, 10.0],
                },
            }
        elif data_days >= 365:
            return {
                'yearly_seasonality': True,
                'cv_initial': '180 days',
                'cv_period':  '30 days',
                'cv_horizon': '30 days',
                # [EDIT_POINT] Ubah kombinasi hyperparameter MEDIUM di sini.
                'param_grid': {
                    'changepoint_prior_scale': [0.01, 0.1],
                    'seasonality_prior_scale': [1.0, 10.0],
                },
            }
        elif data_days >= 90:
            cv_initial_days = max(int(data_days * 0.6), 60)
            return {
                'yearly_seasonality': False,
                'cv_initial': f'{cv_initial_days} days',
                'cv_period':  '14 days',
                'cv_horizon': '14 days',
                # [EDIT_POINT] Ubah kombinasi hyperparameter SHORT di sini.
                'param_grid': {
                    'changepoint_prior_scale': [0.05, 0.1],
                    'seasonality_prior_scale': [5.0, 10.0],
                },
            }
        else:
            # Data < 90 hari: skip cross-val
            return {
                'yearly_seasonality': False,
                'cv_initial':  None,
                'cv_period':   None,
                'cv_horizon':  None,
                # [EDIT_POINT] Ubah fallback hyperparameter data sangat pendek di sini.
                'param_grid': {
                    'changepoint_prior_scale': [0.05],
                    'seasonality_prior_scale': [5.0],
                },
            }

    # =========================================================================
    # TRAINING
    # =========================================================================

    def tune_and_train(self, start_date='2020-01-01'):
        """
        Latih model Prophet dengan grid search adaptif, simpan model dan metrik.
        """
        df = self._get_historical_data(start_date=start_date)
        df = self._add_regressors(df)

        data_days = len(df)
        config    = self._get_training_config(data_days)

        print(
            f"[{self.model_name}] "
            f"data={data_days} hari | "
            f"yearly={config['yearly_seasonality']} | "
            f"cv_initial={config['cv_initial']} | "
            f"grid={len(list(itertools.product(*config['param_grid'].values())))} kombinasi"
        )

        best_rmse       = float('inf')
        best_model      = None
        best_cv_metrics = None

        for values in itertools.product(*config['param_grid'].values()):
            params = dict(zip(config['param_grid'].keys(), values))

            m = Prophet(
                growth='linear',  # kembali ke linear, aman dengan clip
                yearly_seasonality=config['yearly_seasonality'],
                weekly_seasonality=True,
                daily_seasonality=False,
                **params
            )
            m.add_regressor('is_weekend')
            m.add_regressor('is_national_holiday')
            m.add_regressor('is_store_closed')
            m.add_country_holidays(country_name='ID')
            m.fit(df)

            if config['cv_initial'] is not None:
                try:
                    df_cv      = cross_validation(
                        m,
                        initial=config['cv_initial'],
                        period=config['cv_period'],
                        horizon=config['cv_horizon'],
                        disable_tqdm=True,
                    )
                    cv_metrics = performance_metrics(df_cv)
                    rmse       = cv_metrics['rmse'].iloc[-1]

                    if rmse < best_rmse:
                        best_rmse       = rmse
                        best_model      = m
                        best_cv_metrics = cv_metrics

                except Exception as e:
                    print(f"  [skip] params={params} → cross-val error: {e}")
                    continue
            else:
                if best_model is None:
                    best_model = m

        if best_model is None:
            raise RuntimeError(
                f"Tidak ada model yang berhasil dilatih untuk {self.model_name}. "
                f"Data: {data_days} hari."
            )

        # In-sample metrics
        forecast_train = best_model.predict(df)
        y_true         = df['y'].values
        y_pred         = forecast_train['yhat'].values

        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else None

        residuals = y_true - y_pred
        ev = float(1 - np.var(residuals) / np.var(y_true)) if np.var(y_true) > 0 else None

        if best_cv_metrics is not None:
            has_mape  = 'mape'  in best_cv_metrics.columns
            has_smape = 'smape' in best_cv_metrics.columns
            best_metrics = {
                'mae':                float(best_cv_metrics['mae'].iloc[-1]),
                'rmse':               float(best_cv_metrics['rmse'].iloc[-1]),
                'mape':               float(best_cv_metrics['mape'].iloc[-1])  if has_mape  else None,
                'smape':              float(best_cv_metrics['smape'].iloc[-1]) if has_smape else None,
                'r2_score':           round(r2, 4) if r2 is not None else None,
                'explained_variance': round(ev, 4) if ev is not None else None,
                'data_days':          data_days,
                'cv_initial':         config['cv_initial'],
            }
        else:
            best_metrics = {
                'mae':                None,
                'rmse':               None,
                'mape':               None,
                'smape':              None,
                'r2_score':           round(r2, 4) if r2 is not None else None,
                'explained_variance': round(ev, 4) if ev is not None else None,
                'data_days':          data_days,
                'cv_initial':         None,
            }

        error_val   = best_metrics['mape'] if best_metrics['mape'] is not None else best_metrics['smape']
        error_label = 'MAPE' if best_metrics['mape'] is not None else 'sMAPE'
        error_str   = f"{error_label}={error_val:.2f}%" if error_val is not None else "no-cv"
        print(
            f"[{self.model_name}] DONE — "
            f"RMSE={best_metrics['rmse']} | {error_str} | R²={best_metrics['r2_score']}"
        )

        self.model = best_model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        with open(self.metrics_path, 'w') as f:
            json.dump(best_metrics, f, indent=2)

        return self.model

    # =========================================================================
    # LOADING
    # =========================================================================

    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Model tidak ditemukan di {self.model_path}. "
                "Jalankan training dulu: POST /api/inventory/train/start"
            )
        self.model = joblib.load(self.model_path)
        return self.model

    def _load_metrics(self):
        if not os.path.exists(self.metrics_path):
            return None
        with open(self.metrics_path, 'r') as f:
            return json.load(f)

    # =========================================================================
    # PREDICTION
    # =========================================================================

    def predict(self, periods=1, freq='W'):
        if not self.model:
            self.load_model()

        if freq == 'W':
            future_periods = periods * 7
        elif freq == 'M':
            future_periods = periods * 30
        elif freq == 'D':
            future_periods = periods
        else:
            raise ValueError("freq harus 'D' (harian), 'W' (mingguan), atau 'M' (bulanan)")

        future = self.model.make_future_dataframe(periods=future_periods)
        future = self._add_regressors(future)
        forecast = self.model.predict(future)

        last_hist_date = self.model.history['ds'].max()
        daily_rows = forecast[forecast['ds'] > last_hist_date].head(future_periods).copy()

        # Clip negatif
        daily_rows['yhat']       = daily_rows['yhat'].clip(lower=0)
        daily_rows['yhat_lower'] = daily_rows['yhat_lower'].clip(lower=0)
        daily_rows['yhat_upper'] = daily_rows['yhat_upper'].clip(lower=0)

        # --- Agregasi berdasarkan freq ---
        if freq == 'D':
            # Harian tetap seperti biasa
            forecast_array = [
                {
                    "date": row['ds'].strftime('%Y-%m-%d'),
                    "predicted_usage": round(row['yhat'], 2),
                    "lower_bound": round(row['yhat_lower'], 2),
                    "upper_bound": round(row['yhat_upper'], 2),
                }
                for _, row in daily_rows.iterrows()
            ]
            forecast_key = "daily_forecast"

        elif freq == 'W':
            # Kelompokkan per minggu (awal minggu Senin)
            daily_rows['week_start'] = daily_rows['ds'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d'))
            daily_rows['week_end']   = daily_rows['ds'].dt.to_period('W').apply(lambda r: r.end_time.strftime('%Y-%m-%d'))
            grouped = daily_rows.groupby(['week_start', 'week_end']).agg(
                total_yhat       = ('yhat', 'sum'),
                total_yhat_lower = ('yhat_lower', 'sum'),
                total_yhat_upper = ('yhat_upper', 'sum'),
                avg_yhat         = ('yhat', 'mean')
            ).reset_index()
            forecast_array = [
                {
                    "week_start": row['week_start'],
                    "week_end": row['week_end'],
                    "predicted_usage": round(row['total_yhat'], 2),
                    "lower_bound": round(row['total_yhat_lower'], 2),
                    "upper_bound": round(row['total_yhat_upper'], 2),
                    "average_daily_usage": round(row['avg_yhat'], 2),
                }
                for _, row in grouped.iterrows()
            ]
            forecast_key = "weekly_forecast"

        elif freq == 'M':
            # Kelompokkan per bulan
            daily_rows['month_start'] = daily_rows['ds'].dt.to_period('M').apply(lambda r: r.start_time.strftime('%Y-%m-%d'))
            daily_rows['month_end']   = daily_rows['ds'].dt.to_period('M').apply(lambda r: r.end_time.strftime('%Y-%m-%d'))
            grouped = daily_rows.groupby(['month_start', 'month_end']).agg(
                total_yhat       = ('yhat', 'sum'),
                total_yhat_lower = ('yhat_lower', 'sum'),
                total_yhat_upper = ('yhat_upper', 'sum'),
                avg_yhat         = ('yhat', 'mean')
            ).reset_index()
            forecast_array = [
                {
                    "month_start": row['month_start'],
                    "month_end": row['month_end'],
                    "predicted_usage": round(row['total_yhat'], 2),
                    "lower_bound": round(row['total_yhat_lower'], 2),
                    "upper_bound": round(row['total_yhat_upper'], 2),
                    "average_daily_usage": round(row['avg_yhat'], 2),
                }
                for _, row in grouped.iterrows()
            ]
            forecast_key = "monthly_forecast"

        # Forecast summary
        total_all = round(daily_rows['yhat'].sum(), 2)
        avg_all   = round(daily_rows['yhat'].mean(), 2)
        forecast_summary = {
            f"total_predicted_usage_next_{future_periods}_days": total_all,
            f"average_daily_usage_next_{future_periods}_days": avg_all
        }

        # Prediction analysis (dari data harian)
        highest = daily_rows.loc[daily_rows['yhat'].idxmax()]
        lowest  = daily_rows.loc[daily_rows['yhat'].idxmin()]
        prediction_analysis = {
            "highest_prediction_day":   highest['ds'].strftime('%Y-%m-%d'),
            "highest_prediction_value": round(highest['yhat'], 2),
            "lowest_prediction_day":    lowest['ds'].strftime('%Y-%m-%d'),
            "lowest_prediction_value":  round(lowest['yhat'], 2)
        }

        # Confidence
        metrics = self._load_metrics()
        error_metric = None
        if metrics:
            error_metric = metrics.get('mape') if metrics.get('mape') is not None else metrics.get('smape')
        if error_metric is not None:
            confidence_score = max(0.0, min(100.0, 100 - error_metric))
            if confidence_score >= 85:
                confidence_level = "HIGH"
            elif confidence_score >= 70:
                confidence_level = "MEDIUM"
            else:
                confidence_level = "LOW"
        else:
            confidence_score = 0
            confidence_level = "UNKNOWN"
        model_confidence = {
            "confidence_score": round(confidence_score, 2),
            "confidence_level": confidence_level
        }

        # Gabungkan
        result = {
            "store_id":            self.store_id,
            "ingredient_id":       self.ingredient_id,
            "metrics":             metrics,
            "forecast_summary":    forecast_summary,
            "prediction_analysis": prediction_analysis,
            "model_confidence":    model_confidence,
            forecast_key:          forecast_array
        }
        return result
    
    # =========================================================================
    # SAVE TO DATABASE
    # ========================================================================= 

    def save_all_forecasts(self, periods=4, freq='W'):
        """
        Prediksi sekali, simpan ke tiga tabel:
        1. forecast_predictions  (dashboard)
        2. forecast_runs         (tracking)
        3. forecast_results      (evaluasi)
        """
        # 1. Prediksi satu kali
        try:
            result = self.predict(periods=periods, freq=freq)
        except Exception as e:
            print(f"[ERROR] Gagal prediksi {self.model_name}: {e}")
            return False

        metrics = result.get('metrics', {}) or {}
        summary = result.get('forecast_summary', {})

        # 2. Tentukan array forecast
        if freq == 'D':
            forecast_array = result.get('daily_forecast', [])
            horizon_label = "daily"
            horizon_days = periods
            date_key = 'date'
        elif freq == 'W':
            forecast_array = result.get('weekly_forecast', [])
            horizon_label = "weekly"
            horizon_days = periods * 7
            date_key = 'week_start'
        elif freq == 'M':
            forecast_array = result.get('monthly_forecast', [])
            horizon_label = "monthly"
            horizon_days = periods * 30
            date_key = 'month_start'
        else:
            return False

        if not forecast_array:
            print("[ERROR] Array forecast kosong")
            return False

        # 3. Siapkan data untuk forecast_predictions
        model_version = "1.0.0"  # bisa diganti dari config atau hasil tuning nanti
        pred_rows = []
        for item in forecast_array:
            pred_rows.append({
                "store_id":        self.store_id,
                "module":          "inventory",
                "horizon_label":   horizon_label,
                "horizon_days":    horizon_days,
                "prediction_date": item[date_key],
                "predicted_value": item.get('predicted_usage', 0.0),
                "lower_bound":     item.get('lower_bound') if item.get('lower_bound') is not None else 0.0,
                "upper_bound":     item.get('upper_bound') if item.get('upper_bound') is not None else 0.0,
                "mae":             metrics.get('mae') if metrics.get('mae') is not None else 0.0,
                "rmse":            metrics.get('rmse') if metrics.get('rmse') is not None else 0.0,
                "mape":            metrics.get('mape') if metrics.get('mape') is not None else 0.0,
                "model_version":   model_version,
            })

        # 4. Kirim ke forecast_predictions
        url_pred = f"{Config.BACKEND_API_URL}/forecast-predictions"
        try:
            resp = requests.post(url_pred, json={"predictions": pred_rows}, headers=Config.backend_headers(), timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            print(f"[SAVED] {len(pred_rows)} baris → forecast_predictions")
        except requests.RequestException as e:
            print(f"[ERROR] Gagal simpan forecast_predictions: {e}")
            # tetap lanjut ke tabel lain (optional)
        
        # 5. Siapkan data untuk forecast_runs
        if self.model and hasattr(self.model, 'history') and not self.model.history.empty:
            hist = self.model.history
            train_start = hist['ds'].min().strftime('%Y-%m-%d')
            train_end   = hist['ds'].max().strftime('%Y-%m-%d')
        else:
            train_start = train_end = 'unknown'

        predict_start = forecast_array[0][date_key]
        predict_end   = forecast_array[-1][date_key]

        # menyiapkan json untuk metrics dan summary
        now = datetime.now(timezone.utc).isoformat()
        metrics_str = json.dumps(metrics) if metrics else "{}"
        summary_str = json.dumps(summary) if summary else "{}"

        data_quality = {
            "date_range": {
                "start": train_start,
                "end": train_end
            },
            "training_rows": len(self.model.history) if self.model and hasattr(self.model, 'history') else 0,
            "missing_dates_filled": 0
        }
        data_quality_str = json.dumps(data_quality)

        run_payload = {
            "store_id":          self.store_id,
            "forecast_type":     "inventory",
            "horizon_label":     horizon_label,
            "horizon_days":      horizon_days,
            "granularity":       "daily",
            "model_name":        "prophet",
            "model_version":     model_version,
            "feature_version":   "v1",
            "train_start_date":  train_start,
            "train_end_date":    train_end,
            "predict_start_date": predict_start,
            "predict_end_date":   predict_end,
            "metrics":           metrics_str,
            "summary":           summary_str,
            "data_quality":      data_quality_str,
            "status":            "success",
            "started_at":        now,
            "finished_at":       now
        }

        # 6. Kirim ke forecast_runs
        url_runs = f"{Config.BACKEND_API_URL}/forecast-runs"
        run_id = None
        try:
            resp = requests.post(url_runs, json=run_payload, headers=Config.backend_headers(), timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            run_data = resp.json()
            run_id = run_data.get('run_id')
            if not run_id:
                print("[ERROR] run_id tidak ditemukan")
                return False
            print(f"[SAVED] forecast_runs run_id={run_id}")
        except requests.RequestException as e:
            print(f"[ERROR] Gagal simpan forecast_runs: {e}")
            return False

        # 7. Siapkan data untuk forecast_results
        results = []
        for item in forecast_array:
            # ambil confidence_score dari hasil predict
            conf_score = result.get('model_confidence', {}).get('confidence_score', 0)
            # bulatkan ke integer (atau biarkan float – sesuaikan dengan tipe di DB)
            conf_level = int(round(conf_score))

            results.append({
                "target_date":      item[date_key],
                "predicted_value":  item.get('predicted_usage', 0.0),
                "lower_bound":      item.get('lower_bound'),
                "upper_bound":      item.get('upper_bound'),
                "confidence_level": conf_level,   # diambil dari metrik asli
                "item_id":          self.ingredient_id,
                "item_type":        "ingredient"
            })

        # 8. Kirim ke forecast_results
        url_results = f"{Config.BACKEND_API_URL}/forecast-results"
        try:
            resp = requests.post(url_results, json={"run_id": run_id, "results": results}, headers=Config.backend_headers(), timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            print(f"[SAVED] {len(results)} baris → forecast_results untuk run_id={run_id}")
            return True
        except requests.RequestException as e:
            print(f"[ERROR] Gagal simpan forecast_results: {e}")
            return False