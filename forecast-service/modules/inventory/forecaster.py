import pandas as pd
import numpy as np
from prophet import Prophet
import joblib
import holidays
import os
import json
import requests
from datetime import datetime
from config import Config

class InventoryForecaster:
    def __init__(self, store_id, ingredient_id, model_dir=None):
        if model_dir is None:
            model_dir = Config.MODEL_DIR
        self.store_id = store_id
        self.ingredient_id = ingredient_id
        self.model_name = f"model_store{store_id}_ingr{ingredient_id}"
        self.model_path = os.path.join(model_dir, 'inventory', f"{self.model_name}.pkl")
        self.metrics_path = os.path.join(model_dir, 'inventory', f"metrics_{self.model_name}.json")
        self.model = None
        self.id_holidays = holidays.ID()   # Kalender libur Indonesia

    # ========== DATA RETRIEVAL ==========
    def _get_historical_data(self, start_date='2020-01-01', end_date='2026-12-31'):
        """Ambil data dari API Go, agregasi harian SUM(reduced)."""
        url = f"{Config.BACKEND_API_URL}/ingredient-stock-histories"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Gagal mengambil data dari API: {e}")

        data = resp.json()
        if isinstance(data, dict) and 'data' in data:
            records = data['data']
        else:
            records = data

        if not records:
            raise ValueError("Data kosong dari API")

        df = pd.DataFrame(records)
        df = df[(df['m_store_id'] == self.store_id) & (df['m_food_ingredient_id'] == self.ingredient_id)]
        if df.empty:
            raise ValueError(f"Tidak ada data untuk pasangan {self.store_id}-{self.ingredient_id}")

        df['date'] = pd.to_datetime(df['date'])
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        df = df[mask]

        # Hanya pemakaian (reduced > 0)
        df = df[df['reduced'] > 0]

        if df.empty:
            raise ValueError(f"Tidak ada data pemakaian pada rentang {start_date} - {end_date}")

        # Agregasi harian
        daily = df.groupby(df['date'].dt.date)['reduced'].sum().reset_index()
        daily.columns = ['ds', 'y']
        daily['ds'] = pd.to_datetime(daily['ds'])

        # Isi hari tanpa transaksi dengan 0
        full_range = pd.date_range(start=daily['ds'].min(), end=end_date, freq='D')
        df_full = pd.DataFrame({'ds': full_range})
        df_final = df_full.merge(daily, on='ds', how='left')
        df_final['y'] = df_final['y'].fillna(0)
        return df_final[['ds', 'y']]

    # ========== FEATURE ENGINEERING ==========
    def _add_regressors(self, df):
        """Tambahkan fitur weekend, hari libur nasional, dan placeholder libur toko."""
        df = df.copy()
        df['is_weekend'] = df['ds'].dt.dayofweek.isin([5, 6]).astype(int)
        df['is_national_holiday'] = df['ds'].apply(lambda x: 1 if x in self.id_holidays else 0)
        df['is_store_closed'] = 0   # opsional, default tidak ada libur toko
        return df

    # ========== TRAINING ==========
    def tune_and_train(self, start_date='2020-01-01'):
        """Latih model dengan grid search kecil, simpan model & metrik evaluasi."""
        df = self._get_historical_data(start_date=start_date)
        df = self._add_regressors(df)

        param_grid = {
            'changepoint_prior_scale': [0.01, 0.05, 0.1],
            'seasonality_prior_scale': [1.0, 5.0, 10.0]
        }
        best_rmse = float('inf')
        best_model = None
        best_metrics = None
        from prophet.diagnostics import cross_validation, performance_metrics
        import itertools

        for params in (dict(zip(param_grid.keys(), v)) for v in itertools.product(*param_grid.values())):
            m = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                **params
            )
            m.add_regressor('is_weekend')
            m.add_regressor('is_national_holiday')
            m.add_regressor('is_store_closed')
            m.add_country_holidays(country_name='ID')
            m.fit(df)

            try:
                df_cv = cross_validation(m, initial='365 days', period='30 days', horizon='30 days')
                metrics = performance_metrics(df_cv)
                rmse = metrics['rmse'].iloc[-1]
                # Simpan metrik jika ini yang terbaik
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_model = m
                    best_metrics = {
                        'mae': metrics['mae'].iloc[-1],
                        'rmse': metrics['rmse'].iloc[-1],
                        'mape': metrics['mape'].iloc[-1],
                        'r2_score': None,   # Prophet tidak langsung, kita bisa hitung manual jika perlu
                        'explained_variance': None
                    }
            except Exception:
                continue

        if best_model is None:
            raise RuntimeError("Tidak ada model yang berhasil dilatih.")

        # Hitung tambahan metrik dari data latih (opsional)
        # forecast_train = best_model.predict(df)
        # r2 = 1 - np.sum((df['y'] - forecast_train['yhat'])**2) / np.sum((df['y'] - df['y'].mean())**2)
        # best_metrics['r2_score'] = r2
        # best_metrics['explained_variance'] = ...

        print(f"Best params for {self.model_name}: RMSE={best_rmse:.2f}")
        self.model = best_model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)

        # Simpan metrik ke JSON
        with open(self.metrics_path, 'w') as f:
            json.dump(best_metrics, f, indent=2)
        return self.model

    # ========== LOADING ==========
    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}. Train it first.")
        self.model = joblib.load(self.model_path)
        return self.model

    def _load_metrics(self):
        if not os.path.exists(self.metrics_path):
            return None
        with open(self.metrics_path, 'r') as f:
            return json.load(f)

    # ========== PREDICTION ==========
    def predict(self, periods=1, freq='W'):
        """
        Menghasilkan prediksi dalam format dictionary lengkap.
        freq: 'W' (mingguan) atau 'M' (bulanan) – tetap menyertakan daily_forecast.
        """
        if not self.model:
            self.load_model()

        # Hitung jumlah hari yang diminta
        if freq == 'W':
            future_periods = periods * 7
        elif freq == 'M':
            future_periods = periods * 30
        else:
            raise ValueError("freq must be 'W' or 'M'")

        future = self.model.make_future_dataframe(periods=future_periods)
        future = self._add_regressors(future)
        forecast = self.model.predict(future)

        last_hist_date = self.model.history['ds'].max()
        future_forecast = forecast[forecast['ds'] > last_hist_date].copy()

        # Ambil hanya sejumlah periode yang diminta (untuk daily_forecast)
        daily_rows = future_forecast.head(future_periods)

        # Bangun daily_forecast array
        daily_forecast = []
        for _, row in daily_rows.iterrows():
            daily_forecast.append({
                "date": row['ds'].strftime('%Y-%m-%d'),
                "predicted_usage": round(row['yhat'], 2),
                "lower_bound": round(row['yhat_lower'], 2),
                "upper_bound": round(row['yhat_upper'], 2)
            })

        # Summary (total dan rata‑rata)
        total_predicted = round(daily_rows['yhat'].sum(), 2)
        average_daily = round(daily_rows['yhat'].mean(), 2)
        forecast_summary = {
            f"total_predicted_usage_next_{future_periods}_days": total_predicted,
            f"average_daily_usage_next_{future_periods}_days": average_daily
        }

        # Analysis: hari tertinggi & terendah dari daily_rows
        highest = daily_rows.loc[daily_rows['yhat'].idxmax()]
        lowest = daily_rows.loc[daily_rows['yhat'].idxmin()]
        prediction_analysis = {
            "highest_prediction_day": highest['ds'].strftime('%Y-%m-%d'),
            "highest_prediction_value": round(highest['yhat'], 2),
            "lowest_prediction_day": lowest['ds'].strftime('%Y-%m-%d'),
            "lowest_prediction_value": round(lowest['yhat'], 2)
        }

        # Confidence dari metrik tersimpan
        metrics = self._load_metrics()
        if metrics and metrics.get('mape') is not None:
            mape = metrics['mape']
            confidence_score = max(0, 100 - mape)   # seperti modul visitor
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

        # Gabungkan semua
        result = {
            "store_id": self.store_id,
            "ingredient_id": self.ingredient_id,
            "metrics": metrics,
            "forecast_summary": forecast_summary,
            "prediction_analysis": prediction_analysis,
            "model_confidence": model_confidence,
            "daily_forecast": daily_forecast
        }
        return result