import pandas as pd
import numpy as np
from prophet import Prophet
import joblib
import holidays
import os
import requests
from config import Config

class InventoryForecaster:
    def __init__(self, store_id, ingredient_id, model_dir=None):
        if model_dir is None:
            model_dir = Config.MODEL_DIR
        self.store_id = store_id
        self.ingredient_id = ingredient_id
        self.model_name = f"model_store{store_id}_ingr{ingredient_id}"
        self.model_path = os.path.join(model_dir, 'inventory', f"{self.model_name}.pkl")
        self.model = None
        self.id_holidays = holidays.ID()

    def _get_historical_data(self, start_date='2020-01-01', end_date='2026-12-31'):
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

        # Gunakan semua pengurangan stok (reduced > 0)
        df = df[df['reduced'] > 0]

        if df.empty:
            raise ValueError(f"Tidak ada data pengurangan stok pada rentang {start_date} - {end_date}")

        daily = df.groupby(df['date'].dt.date)['reduced'].sum().reset_index()
        daily.columns = ['ds', 'y']
        daily['ds'] = pd.to_datetime(daily['ds'])

        full_range = pd.date_range(start=daily['ds'].min(), end=end_date, freq='D')
        df_full = pd.DataFrame({'ds': full_range})
        df_final = df_full.merge(daily, on='ds', how='left')
        df_final['y'] = df_final['y'].fillna(0)
        return df_final[['ds', 'y']]

    def _add_regressors(self, df):
        df = df.copy()
        df['is_weekend'] = df['ds'].dt.dayofweek.isin([5, 6]).astype(int)
        df['is_national_holiday'] = df['ds'].apply(lambda x: 1 if x in self.id_holidays else 0)
        df['is_store_closed'] = 0
        return df

    def tune_and_train(self, start_date='2020-01-01'):
        df = self._get_historical_data(start_date=start_date)
        df = self._add_regressors(df)

        param_grid = {
            'changepoint_prior_scale': [0.01, 0.05, 0.1],
            'seasonality_prior_scale': [1.0, 5.0, 10.0]
        }
        best_rmse = float('inf')
        best_model = None
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
            except Exception:
                rmse = 99999

            if rmse < best_rmse:
                best_rmse = rmse
                best_model = m

        print(f"Best params for {self.model_name}: RMSE={best_rmse:.2f}")
        self.model = best_model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        return self.model

    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}. Train it first.")
        self.model = joblib.load(self.model_path)
        return self.model

    def predict(self, periods, freq='W'):
        if not self.model:
            self.load_model()

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

        if freq == 'W':
            future_forecast['week'] = future_forecast['ds'].dt.to_period('W').apply(lambda r: r.start_time)
            grouped = future_forecast.groupby('week')[['yhat', 'yhat_lower', 'yhat_upper']].sum().reset_index()
            grouped = grouped.rename(columns={'week': 'ds'})
            result = grouped.tail(periods)
        elif freq == 'M':
            future_forecast['month'] = future_forecast['ds'].dt.to_period('M').apply(lambda r: r.start_time)
            grouped = future_forecast.groupby('month')[['yhat', 'yhat_lower', 'yhat_upper']].sum().reset_index()
            grouped = grouped.rename(columns={'month': 'ds'})
            result = grouped.tail(periods)

        result['store_id'] = self.store_id
        result['ingredient_id'] = self.ingredient_id
        return result[['ds', 'store_id', 'ingredient_id', 'yhat', 'yhat_lower', 'yhat_upper']]