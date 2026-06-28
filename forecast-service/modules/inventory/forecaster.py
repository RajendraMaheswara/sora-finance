"""Inventory forecasting for ingredients using Prophet (store-level joblib)."""

import itertools
import json
import os

import holidays
import joblib
import numpy as np
from scipy import stats as sp_stats
import pandas as pd
import requests
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics

from config import Config
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple


class InventoryForecaster:
    def __init__(self, store_id, ingredient_id, freq, model_dir=None):
        """
        Parameters
        ----------
        store_id : str
        ingredient_id : str
        freq : str  {'D', 'W', 'M'}  – horizon yang diminta
        model_dir : str or None
        """
        if model_dir is None:
            model_dir = Config.MODEL_DIR

        self.store_id      = store_id
        self.ingredient_id = ingredient_id
        self.freq          = freq          # diperlukan untuk memilih file joblib yang benar
        self.model         = None
        self.id_holidays   = holidays.ID()

        # Nama horizon untuk penamaan file (daily/weekly/monthly)
        horizon_label = {'D': 'daily', 'W': 'weekly', 'M': 'monthly'}[freq]

        # Path file joblib yang berisi dict {ingredient_id: model}
        self.store_model_path = os.path.join(
            model_dir, 'inventory',
            f"inventory_{horizon_label}_model_store_{store_id}.joblib"
        )

        # Path metrik per ingredient (opsional, untuk debug)
        self.metrics_path = os.path.join(
            model_dir, 'inventory',
            f"metrics_store_{store_id}_ingr_{ingredient_id}.json"
        )

    # =========================================================================
    # BACKEND + PERIOD HELPERS
    # =========================================================================
    def _backend_base_url(self) -> str:
        return getattr(Config, 'GOLANG_INTERNAL_API_BASE_URL', Config.GOLANG_API_BASE_URL).rstrip('/')

    def _extract_items(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ('data', 'items', 'results'):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _same_store(self, item: Dict[str, Any]) -> bool:
        value = item.get('m_store_id') or item.get('store_id') or item.get('storeId') or item.get('mStoreId')
        return str(value) == str(self.store_id)

    def _backend_get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self._backend_base_url()}/{endpoint.lstrip('/')}"
        resp = requests.get(
            url,
            params=params,
            headers=Config.backend_headers(),
            timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def _backend_post(self, endpoint: str, payload: Dict[str, Any]) -> Any:
        url = f"{self._backend_base_url()}/{endpoint.lstrip('/')}"
        resp = requests.post(
            url,
            json=payload,
            headers=Config.backend_headers(),
            timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def _fetch_store_operational_hours(self) -> List[Dict[str, Any]]:
        try:
            data = self._backend_get('store-operational-hours', params={'store_id': self.store_id})
            items = self._extract_items(data)
            filtered = [item for item in items if self._same_store(item)]
            return filtered or items
        except Exception as exc:
            print(f"[WARN] operational hours gagal diambil, fallback open 24h: {exc}")
            return []

    def _now_jakarta(self) -> datetime:
        return datetime.now(ZoneInfo(getattr(Config, 'FORECAST_SCHEDULER_TIMEZONE', 'Asia/Jakarta')))

    def _bool_value(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {'true', 't', '1', 'yes', 'y', 'on'}:
            return True
        if text in {'false', 'f', '0', 'no', 'n', 'off'}:
            return False
        return default

    def _seconds_from_time_like(self, value: Any) -> Optional[int]:
        if value is None or pd.isna(value):
            return None
        ts = pd.to_datetime(value, errors='coerce')
        if pd.isna(ts):
            return None
        return int(ts.hour) * 3600 + int(ts.minute) * 60 + int(ts.second)

    def _calculate_open_duration_hours(self, is_active: bool, open_time: Any, close_time: Any) -> float:
        if not is_active:
            return 0.0
        open_seconds = self._seconds_from_time_like(open_time)
        close_seconds = self._seconds_from_time_like(close_time)
        if open_seconds is None or close_seconds is None:
            return 24.0
        if close_seconds == open_seconds:
            return 24.0
        if close_seconds > open_seconds:
            duration_seconds = close_seconds - open_seconds
        else:
            duration_seconds = (24 * 3600 - open_seconds) + close_seconds
        return round(max(0.0, min(24.0, duration_seconds / 3600.0)), 2)

    def _operational_record_for_date(self, target_date: date, operational_hours: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not operational_hours:
            return None
        ts = pd.Timestamp(target_date)
        candidates = {int(ts.dayofweek), int(ts.isoweekday()), int(ts.isoweekday()) % 7}
        for record in operational_hours or []:
            try:
                day_key = int(record.get('day_of_week', record.get('dayOfWeek')))
            except Exception:
                continue
            if day_key in candidates:
                return record
        return None

    def _store_is_open_on_date(self, target_date: date, operational_hours: List[Dict[str, Any]]) -> bool:
        if not operational_hours:
            return True
        record = self._operational_record_for_date(target_date, operational_hours)
        if record is None:
            return True
        if not self._bool_value(record.get('is_active', record.get('isActive')), default=False):
            return False
        duration = self._calculate_open_duration_hours(
            is_active=True,
            open_time=record.get('open_time', record.get('openTime')),
            close_time=record.get('close_time', record.get('closeTime')),
        )
        return duration > 0

    def _operational_cutoff_datetime(self, target_date: date, operational_hours: List[Dict[str, Any]]) -> datetime:
        jakarta = ZoneInfo(getattr(Config, 'FORECAST_SCHEDULER_TIMEZONE', 'Asia/Jakarta'))
        record = self._operational_record_for_date(target_date, operational_hours)
        if not operational_hours or record is None:
            return (
                datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tzinfo=jakarta)
                + timedelta(minutes=getattr(Config, 'FORECAST_24H_RUN_SCHEDULER_MINUTES', 120))
            )
        is_active = self._bool_value(record.get('is_active', record.get('isActive')), default=False)
        if not is_active:
            return datetime.combine(target_date, datetime.min.time(), tzinfo=jakarta)
        open_seconds = self._seconds_from_time_like(record.get('open_time', record.get('openTime')))
        close_seconds = self._seconds_from_time_like(record.get('close_time', record.get('closeTime')))
        if open_seconds is None or close_seconds is None or open_seconds == close_seconds:
            return (
                datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tzinfo=jakarta)
                + timedelta(minutes=getattr(Config, 'FORECAST_24H_RUN_SCHEDULER_MINUTES', 120))
            )
        close_day = target_date + timedelta(days=1) if close_seconds <= open_seconds else target_date
        close_dt = datetime.combine(close_day, datetime.min.time(), tzinfo=jakarta) + timedelta(seconds=close_seconds)
        return close_dt + timedelta(minutes=getattr(Config, 'FORECAST_AFTER_CLOSE_SCHEDULER_MINUTES', 60))

    def _latest_complete_day_by_operational_hours(
        self,
        operational_hours: List[Dict[str, Any]],
        now_jakarta: Optional[datetime] = None,
    ) -> date:
        now = now_jakarta or self._now_jakarta()
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo(getattr(Config, 'FORECAST_SCHEDULER_TIMEZONE', 'Asia/Jakarta')))
        for offset in range(0, 14):
            candidate = now.date() - timedelta(days=offset)
            if not self._store_is_open_on_date(candidate, operational_hours):
                continue
            if now >= self._operational_cutoff_datetime(candidate, operational_hours):
                return candidate
        return now.date() - timedelta(days=1)

    def _next_monday_after(self, value: date) -> date:
        days = (7 - value.weekday()) % 7
        if days == 0:
            days = 7
        return value + timedelta(days=days)

    def _first_day_next_month_after(self, value: date) -> date:
        return (pd.Timestamp(value.replace(day=1)) + pd.DateOffset(months=1)).date()

    def _resolve_forecast_start_meta(
        self,
        *,
        last_actual_date: Optional[date],
        operational_hours: List[Dict[str, Any]],
        requested_start_date: Optional[date],
        horizon_label: str,
    ) -> Dict[str, Any]:
        if requested_start_date is not None:
            return {
                'forecast_start_date': requested_start_date,
                'start_date_source': 'manual_body',
                'last_actual_date': last_actual_date,
                'business_cutoff_rule': 'manual_start_date',
            }

        latest_complete_day = self._latest_complete_day_by_operational_hours(operational_hours)
        next_after_complete_day = latest_complete_day + timedelta(days=1)
        next_after_actual = last_actual_date + timedelta(days=1) if last_actual_date is not None else None
        candidate_start = max([d for d in [next_after_complete_day, next_after_actual] if d is not None])

        if horizon_label == 'weekly':
            forecast_start = self._next_monday_after(latest_complete_day)
            if forecast_start < candidate_start:
                forecast_start = self._next_monday_after(candidate_start - timedelta(days=1))
            start_date_source = 'auto_weekly_complete_period'
            business_cutoff_rule = 'weekly_after_complete_operational_sunday_start_monday'
        elif horizon_label == 'monthly':
            forecast_start = self._first_day_next_month_after(latest_complete_day)
            if forecast_start < candidate_start:
                forecast_start = self._first_day_next_month_after(candidate_start)
            start_date_source = 'auto_monthly_complete_period'
            business_cutoff_rule = 'monthly_after_complete_operational_month_start_first_day'
        else:
            forecast_start = candidate_start
            start_date_source = 'auto_daily_complete_period'
            business_cutoff_rule = 'daily_after_close_or_24h_cutoff'

        return {
            'forecast_start_date': forecast_start,
            'start_date_source': start_date_source,
            'last_actual_date': last_actual_date,
            'latest_complete_day': latest_complete_day,
            'business_cutoff_rule': business_cutoff_rule,
        }

    # =========================================================================
    # DATA RETRIEVAL
    # =========================================================================
    def _get_historical_data(self, start_date='2020-01-01', end_date=None):
        if end_date is None:
            end_date = pd.Timestamp.now().strftime('%Y-%m-%d')

        try:
            data = self._backend_get('ingredient-stock-histories', params={'store_id': self.store_id})
        except requests.RequestException as e:
            raise ValueError(f"Gagal mengambil data dari API backend internal: {e}")

        records = self._extract_items(data)
        if not records:
            raise ValueError("Data kosong dari API")

        df = pd.DataFrame(records)
        df = df[(df['m_store_id'] == self.store_id) &
                (df['m_food_ingredient_id'] == self.ingredient_id)]
        if df.empty:
            raise ValueError(f"Tidak ada data untuk pasangan {self.store_id}-{self.ingredient_id}")

        df['date'] = pd.to_datetime(df['date'])
        df['date'] = df['date'].dt.tz_localize(None)
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        df = df[df['reduced'] >= 0]
        if df.empty:
            raise ValueError(f"Tidak ada data pemakaian pada rentang {start_date} - {end_date}")

        daily = df.groupby(df['date'].dt.date)['reduced'].sum().reset_index()
        daily.columns = ['ds', 'y']
        daily['ds'] = pd.to_datetime(daily['ds'])

        max_actual_date = daily['ds'].max()

        # Samakan dengan visitors: hanya pakai operational day yang sudah complete.
        operational_hours = self._fetch_store_operational_hours()
        latest_complete_day = self._latest_complete_day_by_operational_hours(operational_hours)
        max_actual_date = min(max_actual_date, pd.Timestamp(latest_complete_day))

        # Pemotongan Period Complete sesuai freq
        if self.freq == 'W':
            # Cari hari Minggu terakhir (dayofweek == 6)
            if max_actual_date.dayofweek != 6:
                offset = max_actual_date.dayofweek + 1
                max_actual_date = max_actual_date - pd.Timedelta(days=offset)
        elif self.freq == 'M':
            # Cari akhir bulan terakhir
            if not max_actual_date.is_month_end:
                max_actual_date = max_actual_date - pd.offsets.MonthEnd(1)

        daily = daily[daily['ds'] <= max_actual_date]
        if daily.empty:
            raise ValueError(f"Tidak ada data tersisa setelah pemotongan periode komplit (freq={self.freq})")

        full_range = pd.date_range(start=daily['ds'].min(), end=max_actual_date, freq='D')
        df_final   = pd.DataFrame({'ds': full_range}).merge(daily, on='ds', how='left')
        df_final['y'] = df_final['y'].fillna(0)

        # Hitung zero_ratio sebelum cleaning (untuk metrik kualitas data)
        zero_ratio = float((df_final['y'] == 0).mean())

        # --- Fase 0.3: Deteksi stockout tersembunyi ---
        # Zero berturut > 3 hari = kemungkinan stockout, bukan demand nol sesungguhnya
        is_zero = df_final['y'] == 0
        zero_groups = (is_zero != is_zero.shift()).cumsum()
        zero_streak = is_zero.groupby(zero_groups).transform('sum') * is_zero
        stockout_mask = zero_streak > 3
        stockout_days = int(stockout_mask.sum())
        if stockout_days > 0:
            df_final.loc[stockout_mask, 'y'] = np.nan
            print(f"  [clean] {stockout_days} hari stockout terdeteksi \u2192 NaN")

        # --- Fase 0.5: Deteksi outlier ekstrem ---
        outliers_nullified = 0
        valid_y = df_final['y'].dropna()
        if len(valid_y) > 10:
            z_scores = np.abs(sp_stats.zscore(valid_y.values))
            outlier_idx = valid_y.index[z_scores > 3.5]
            outliers_nullified = len(outlier_idx)
            if outliers_nullified > 0:
                df_final.loc[outlier_idx, 'y'] = np.nan
                print(f"  [clean] {outliers_nullified} outlier (z>3.5) \u2192 NaN")

        # Simpan info kualitas data sebagai atribut untuk diakses saat training
        self._data_quality_info = {
            'zero_ratio': round(zero_ratio, 4),
            'outliers_nullified': outliers_nullified,
            'stockout_days_nullified': stockout_days,
        }

        return df_final[['ds', 'y']]

    # =========================================================================
    # FEATURE ENGINEERING
    # =========================================================================
    def _add_regressors(self, df):
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
        if data_days >= 730:
            return {
                'yearly_seasonality': True,
                'cv_initial': '365 days', 'cv_period': '30 days', 'cv_horizon': '30 days',
                'param_grid': {
                    'changepoint_prior_scale': [0.01, 0.05, 0.1],
                    'seasonality_prior_scale': [1.0, 5.0, 10.0],
                    'seasonality_mode': ['additive', 'multiplicative'],
                },
            }
        elif data_days >= 365:
            return {
                'yearly_seasonality': True,
                'cv_initial': '180 days', 'cv_period': '30 days', 'cv_horizon': '30 days',
                'param_grid': {
                    'changepoint_prior_scale': [0.01, 0.1],
                    'seasonality_prior_scale': [1.0, 10.0],
                    'seasonality_mode': ['additive', 'multiplicative'],
                },
            }
        elif data_days >= 90:
            cv_initial_days = max(int(data_days * 0.6), 60)
            return {
                'yearly_seasonality': False,
                'cv_initial': f'{cv_initial_days} days', 'cv_period': '14 days', 'cv_horizon': '14 days',
                'param_grid': {
                    'changepoint_prior_scale': [0.05, 0.1],
                    'seasonality_prior_scale': [5.0, 10.0],
                    'seasonality_mode': ['additive', 'multiplicative'],
                },
            }
        else:
            return {
                'yearly_seasonality': False,
                'cv_initial': None, 'cv_period': None, 'cv_horizon': None,
                'param_grid': {
                    'changepoint_prior_scale': [0.05],
                    'seasonality_prior_scale': [5.0],
                    'seasonality_mode': ['additive', 'multiplicative'],
                },
            }

    # =========================================================================
    # TRAINING
    # =========================================================================
    def tune_and_train(self, start_date='2020-01-01'):
        """Latih model Prophet, simpan metrik, KEMBALIKAN model. Tidak simpan .pkl."""
        df = self._get_historical_data(start_date=start_date)
        df = self._add_regressors(df)

        data_days = len(df)
        config    = self._get_training_config(data_days)
        print(f"[{self.store_id}/{self.ingredient_id}] data={data_days} hari | "
              f"yearly={config['yearly_seasonality']} | cv_initial={config['cv_initial']}")

        best_rmse = float('inf')
        best_model = None
        best_cv_metrics = None

        for values in itertools.product(*config['param_grid'].values()):
            params = dict(zip(config['param_grid'].keys(), values))
            m = Prophet(growth='linear',
                        yearly_seasonality=config['yearly_seasonality'],
                        weekly_seasonality=True, daily_seasonality=False, **params)
            m.add_regressor('is_weekend')
            m.add_regressor('is_national_holiday')
            m.add_regressor('is_store_closed')
            m.add_country_holidays(country_name='ID')
            m.fit(df)

            if config['cv_initial'] is not None:
                try:
                    df_cv = cross_validation(m, initial=config['cv_initial'],
                                             period=config['cv_period'], horizon=config['cv_horizon'],
                                             disable_tqdm=True)
                    cv_metrics = performance_metrics(df_cv)
                    rmse = cv_metrics['rmse'].mean()
                    if rmse < best_rmse:
                        best_rmse = rmse
                        best_model = m
                        best_cv_metrics = cv_metrics
                except Exception as e:
                    print(f"  [skip] {params} → cross-val error: {e}")
                    continue
            else:
                if best_model is None:
                    best_model = m

        if best_model is None:
            raise RuntimeError(f"Tidak ada model yang berhasil dilatih untuk "
                               f"{self.store_id}/{self.ingredient_id}. Data: {data_days} hari.")

        # ---- metrics ----
        forecast_train = best_model.predict(df)
        # Exclude NaN rows (stockout/outlier yang di-null-kan) dari kalkulasi R² train
        valid_mask = df['y'].notna().values
        y_true = df['y'].values[valid_mask]
        y_pred = np.clip(forecast_train['yhat'].values[valid_mask], 0, None)
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        r2_train = float(1 - ss_res / ss_tot) if ss_tot > 0 else None
        residuals = y_true - y_pred
        ev_train = float(1 - np.var(residuals) / np.var(y_true)) if np.var(y_true) > 0 else None

        # Data quality info dari fase cleaning
        dq = getattr(self, '_data_quality_info', {})

        if best_cv_metrics is not None:
            # Hitung R² dan EV dari cross-validation (out-of-sample, lebih jujur)
            df_cv_data = cross_validation(best_model, initial=config['cv_initial'],
                                           period=config['cv_period'], horizon=config['cv_horizon'],
                                           disable_tqdm=True)
            cv_y_true = df_cv_data['y'].values
            cv_y_pred = np.clip(df_cv_data['yhat'].values, 0, None)
            cv_ss_res = np.sum((cv_y_true - cv_y_pred) ** 2)
            cv_ss_tot = np.sum((cv_y_true - cv_y_true.mean()) ** 2)
            r2_cv = float(1 - cv_ss_res / cv_ss_tot) if cv_ss_tot > 0 else r2_train
            cv_residuals = cv_y_true - cv_y_pred
            ev_cv = float(1 - np.var(cv_residuals) / np.var(cv_y_true)) if np.var(cv_y_true) > 0 else ev_train

            # MAPE hanya pada hari dengan pemakaian (y > 0) agar tidak terdistorsi
            mask_nonzero = cv_y_true > 0
            if mask_nonzero.any():
                custom_mape = float(np.mean(np.abs((cv_y_true[mask_nonzero] - cv_y_pred[mask_nonzero]) / cv_y_true[mask_nonzero])))
            else:
                custom_mape = None

            # Bias ratio: rasio total forecast vs total actual (Fase 2.1)
            total_actual = float(cv_y_true.sum())
            bias_ratio = round(float(cv_y_pred.sum() / total_actual), 4) if total_actual > 0 else None

            best_metrics = {
                'mae': float(best_cv_metrics['mae'].mean()),
                'rmse': float(best_cv_metrics['rmse'].mean()),
                'mape': custom_mape,
                'smape': float(best_cv_metrics['smape'].mean()) if 'smape' in best_cv_metrics else None,
                'r2_score': round(r2_cv, 4) if r2_cv is not None else (round(r2_train, 4) if r2_train is not None else None),
                'explained_variance': round(ev_cv, 4) if ev_cv is not None else (round(ev_train, 4) if ev_train is not None else None),
                'data_days': data_days,
                'cv_initial': config['cv_initial'],
                'bias_ratio': bias_ratio,
                'zero_ratio': dq.get('zero_ratio'),
                'outliers_nullified': dq.get('outliers_nullified', 0),
                'stockout_days_nullified': dq.get('stockout_days_nullified', 0),
            }
        else:
            best_metrics = {
                'mae': None, 'rmse': None, 'mape': None, 'smape': None,
                'r2_score': round(r2_train, 4) if r2_train is not None else None,
                'explained_variance': round(ev_train, 4) if ev_train is not None else None,
                'data_days': data_days,
                'cv_initial': None,
                'bias_ratio': None,
                'zero_ratio': dq.get('zero_ratio'),
                'outliers_nullified': dq.get('outliers_nullified', 0),
                'stockout_days_nullified': dq.get('stockout_days_nullified', 0),
            }

        # Simpan metrik per ingredient (file kecil, opsional)
        os.makedirs(os.path.dirname(self.metrics_path), exist_ok=True)
        with open(self.metrics_path, 'w') as f:
            json.dump(best_metrics, f, indent=2)

        # JANGAN simpan model .pkl – biarkan trainer yang mengumpulkan
        self.model = best_model
        return best_model

    # =========================================================================
    # LOADING
    # =========================================================================
    def load_model(self):
        """Muat model spesifik ingredient dari file joblib toko."""
        if not os.path.exists(self.store_model_path):
            raise FileNotFoundError(
                f"Model toko tidak ditemukan: {self.store_model_path}. "
                "Jalankan training dulu."
            )
        all_models = joblib.load(self.store_model_path)
        if self.ingredient_id not in all_models:
            raise ValueError(f"Ingredient {self.ingredient_id} tidak ada di model toko.")
        self.model = all_models[self.ingredient_id]
        if self.model is None:
            raise ValueError(f"Model untuk ingredient {self.ingredient_id} adalah None.")
        return self.model

    def _load_metrics(self):
        """Baca metrik dari file JSON per ingredient (jika ada)."""
        if not os.path.exists(self.metrics_path):
            return None
        with open(self.metrics_path, 'r') as f:
            return json.load(f)

    # =========================================================================
    # PREDICTION
    # =========================================================================
    def predict(self, periods=1, freq='W', start_date=None):
        if not self.model:
            self.load_model()

        if freq == 'W':
            future_periods = periods * 7
        elif freq == 'M':
            future_periods = periods * 30
        elif freq == 'D':
            future_periods = periods
        else:
            raise ValueError("freq harus 'D', 'W', atau 'M'")

        import pandas as pd
        horizon_label = {'D': 'daily', 'W': 'weekly', 'M': 'monthly'}[freq]
        last_hist_date = pd.to_datetime(self.model.history['ds'].max())
        requested_start_date = pd.to_datetime(start_date).date() if start_date else None
        operational_hours = self._fetch_store_operational_hours()
        start_meta = self._resolve_forecast_start_meta(
            last_actual_date=last_hist_date.date(),
            operational_hours=operational_hours,
            requested_start_date=requested_start_date,
            horizon_label=horizon_label,
        )
        target_start = pd.Timestamp(start_meta['forecast_start_date'])
        days_diff = (target_start - last_hist_date).days
        total_periods = (days_diff + future_periods) if days_diff > 0 else future_periods

        future = self.model.make_future_dataframe(periods=total_periods)
        future = self._add_regressors(future)
        forecast = self.model.predict(future)

        daily_rows = forecast[forecast['ds'] >= target_start].head(future_periods).copy()

        daily_rows['yhat']       = daily_rows['yhat'].clip(lower=0)
        daily_rows['yhat_lower'] = daily_rows['yhat_lower'].clip(lower=0)
        daily_rows['yhat_upper'] = daily_rows['yhat_upper'].clip(lower=0)

        # Nama hari Indonesia
        _day_names = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']

        if freq == 'D':
            forecast_array = [
                {"date": row['ds'].strftime('%Y-%m-%d'),
                 "day_of_week": _day_names[row['ds'].dayofweek],
                 "is_weekend": row['ds'].dayofweek >= 5,
                 "predicted_usage": round(row['yhat'], 2),
                 "lower_bound": round(row['yhat_lower'], 2),
                 "upper_bound": round(row['yhat_upper'], 2)}
                for _, row in daily_rows.iterrows()
            ]
            date_key_start = 'date'
            date_key_end   = 'date'
        elif freq == 'W':
            daily_rows['period_start'] = daily_rows['ds'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d'))
            daily_rows['period_end']   = daily_rows['ds'].dt.to_period('W').apply(lambda r: r.end_time.strftime('%Y-%m-%d'))
            daily_rows['week_of_year'] = daily_rows['ds'].dt.isocalendar().week.astype(int)
            grouped = daily_rows.groupby(['period_start', 'period_end', 'week_of_year']).agg(
                total_yhat=('yhat', 'sum'), total_yhat_lower=('yhat_lower', 'sum'),
                total_yhat_upper=('yhat_upper', 'sum')
            ).reset_index()
            forecast_array = [
                {"period_start": row['period_start'], "period_end": row['period_end'],
                 "week_of_year": int(row['week_of_year']),
                 "predicted_usage": round(row['total_yhat'], 2),
                 "lower_bound": round(row['total_yhat_lower'], 2),
                 "upper_bound": round(row['total_yhat_upper'], 2)}
                for _, row in grouped.iterrows()
            ]
            date_key_start = 'period_start'
            date_key_end   = 'period_end'
        elif freq == 'M':
            daily_rows['period_start'] = daily_rows['ds'].dt.to_period('M').apply(lambda r: r.start_time.strftime('%Y-%m-%d'))
            daily_rows['period_end']   = daily_rows['ds'].dt.to_period('M').apply(lambda r: r.end_time.strftime('%Y-%m-%d'))
            daily_rows['month_num']    = daily_rows['ds'].dt.month
            grouped = daily_rows.groupby(['period_start', 'period_end', 'month_num']).agg(
                total_yhat=('yhat', 'sum'), total_yhat_lower=('yhat_lower', 'sum'),
                total_yhat_upper=('yhat_upper', 'sum')
            ).reset_index()
            forecast_array = [
                {"period_start": row['period_start'], "period_end": row['period_end'],
                 "month": int(row['month_num']),
                 "predicted_usage": round(row['total_yhat'], 2),
                 "lower_bound": round(row['total_yhat_lower'], 2),
                 "upper_bound": round(row['total_yhat_upper'], 2)}
                for _, row in grouped.iterrows()
            ]
            date_key_start = 'period_start'
            date_key_end   = 'period_end'

        total_all = round(daily_rows['yhat'].sum(), 2)
        avg_all   = round(daily_rows['yhat'].mean(), 2)

        metrics = self._load_metrics()
        if metrics:
            # Blended confidence: gabungan sMAPE, R², EV, dan bias penalty
            scores = []
            smape = metrics.get('smape')
            if smape is not None:
                smape_pct = smape * 100 if smape < 1.0 else smape
                scores.append(max(0.0, 100 - smape_pct))
            else:
                mape = metrics.get('mape')
                if mape is not None:
                    mape_pct = mape * 100 if mape < 1.0 else mape
                    scores.append(max(0.0, 100 - mape_pct))
            r2 = metrics.get('r2_score')
            if r2 is not None and r2 >= 0.10:
                scores.append(r2 * 100.0)
            ev = metrics.get('explained_variance')
            if ev is not None and ev >= 0.10:
                scores.append(ev * 100.0)

            # Penalti bias: skor turun proporsional jika bias_ratio jauh dari 1.0
            bias_ratio = metrics.get('bias_ratio')
            if bias_ratio is not None:
                bias_penalty = max(0.0, (1 - abs(1 - bias_ratio) * 2)) * 100
                scores.append(bias_penalty)

            if scores:
                confidence_score = max(0.0, min(100.0, sum(scores) / len(scores)))
            else:
                confidence_score = 0.0
        else:
            metrics = {}
            confidence_score = 0.0

        confidence_level = int(round(confidence_score))

        # Hitung error_percentage dari sMAPE atau MAPE
        _smape = metrics.get('smape')
        if _smape is not None:
            error_pct = round((_smape * 100 if _smape < 1.0 else _smape), 2)
        else:
            _mape = metrics.get('mape')
            error_pct = round((_mape * 100 if _mape is not None and _mape < 1.0 else (_mape or 0)) , 2)

        # Tentukan forecast start/end date
        if forecast_array:
            fc_start = forecast_array[0].get(date_key_start)
            fc_end   = forecast_array[-1].get(date_key_end)
        else:
            fc_start = fc_end = None

        result = {
            "store_id": self.store_id,
            "ingredient_id": self.ingredient_id,
            "forecast_start_date": fc_start,
            "forecast_end_date": fc_end,
            "last_actual_date": last_hist_date.strftime('%Y-%m-%d'),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "start_date_source": start_meta.get('start_date_source'),
            "business_cutoff_rule": start_meta.get('business_cutoff_rule'),
            "horizon": {
                "count": periods,
                "days": future_periods,
                "label": horizon_label
            },
            "model_metadata": {
                "confidence_level": confidence_level,
                "cv_mae": metrics.get('mae'),
                "cv_rmse": metrics.get('rmse'),
                "error_percentage": error_pct,
                "smape": metrics.get('smape'),
                "mape": metrics.get('mape'),
                "r2_score": metrics.get('r2_score'),
                "explained_variance": metrics.get('explained_variance'),
                "bias_ratio": metrics.get('bias_ratio'),
                "data_days": metrics.get('data_days'),
                "cv_initial": metrics.get('cv_initial'),
                "zero_ratio": metrics.get('zero_ratio'),
                "outliers_nullified": metrics.get('outliers_nullified'),
                "stockout_days_nullified": metrics.get('stockout_days_nullified'),
            },
            "summary": {
                "average_predicted_usage": avg_all,
                "forecast_count": len(forecast_array),
                "total_predicted_usage": total_all
            },
            "forecasts": forecast_array
        }
        return result

    # =========================================================================
    # SAVE TO DATABASE
    # =========================================================================
    def _parse_run_id(self, response: Any) -> Optional[int]:
        if not isinstance(response, dict):
            return None
        raw = (
            response.get('run_id')
            or (response.get('data') or {}).get('run_id')
            or (response.get('data') or {}).get('id')
            or response.get('id')
        )
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _history_training_range(self) -> Tuple[date, date, int]:
        if not self.model:
            self.load_model()
        if self.model and hasattr(self.model, 'history') and not self.model.history.empty:
            hist = self.model.history.copy()
            dates = pd.to_datetime(hist['ds'], errors='coerce').dropna()
            if not dates.empty:
                return dates.min().date(), dates.max().date(), int(len(hist))
        today = datetime.now(timezone.utc).date()
        return today, today, 0

    def _forecast_item_target_date(self, item: Dict[str, Any], horizon_label: str) -> str:
        if horizon_label == 'daily':
            return str(item.get('date'))
        return str(item.get('period_start'))

    def save_forecast_result(self, forecast_result: Dict[str, Any]) -> Dict[str, Any]:
        """Simpan output predict() ke backend internal forecast_runs/forecast_results.

        Method ini sengaja hanya mengubah jalur save/orchestration. Perhitungan
        Prophet, cleaning stockout/outlier, dan agregasi daily/weekly/monthly
        tetap mengikuti logic inventory yang sudah ada.
        """
        forecast_array = forecast_result.get('forecasts') or []
        if not forecast_array:
            raise ValueError('Forecast kosong, tidak ada data untuk disimpan.')

        horizon = forecast_result.get('horizon') or {}
        horizon_label = str(horizon.get('label') or 'daily').lower()
        horizon_count = int(horizon.get('count') or len(forecast_array))
        predict_start = str(forecast_result.get('forecast_start_date'))
        predict_end = str(forecast_result.get('forecast_end_date'))
        horizon_days = _days = None
        try:
            horizon_days = (date.fromisoformat(predict_end[:10]) - date.fromisoformat(predict_start[:10])).days + 1
        except Exception:
            horizon_days = int(horizon.get('days') or len(forecast_array))

        train_start, train_end, training_rows = self._history_training_range()
        model_meta = forecast_result.get('model_metadata') or {}
        summary = dict(forecast_result.get('summary') or {})
        summary.update({
            'module': 'inventory',
            'horizon_label': horizon_label,
            'horizon_count': horizon_count,
            'horizon_days': horizon_days,
            'forecast_start_date': predict_start,
            'forecast_end_date': predict_end,
            'start_date_source': forecast_result.get('start_date_source'),
            'last_actual_date': forecast_result.get('last_actual_date'),
            'business_cutoff_rule': forecast_result.get('business_cutoff_rule'),
            'ingredient_id': self.ingredient_id,
            'prediction_count': len(forecast_array),
            'generated_at': forecast_result.get('generated_at'),
        })
        metrics = {
            'metric_horizon': horizon_label,
            'mae': model_meta.get('cv_mae'),
            'rmse': model_meta.get('cv_rmse'),
            'mape': model_meta.get('mape'),
            'smape': model_meta.get('smape'),
            'error_percentage': model_meta.get('error_percentage'),
            'confidence_level': model_meta.get('confidence_level'),
            'r2_score': model_meta.get('r2_score'),
            'explained_variance': model_meta.get('explained_variance'),
            'bias_ratio': model_meta.get('bias_ratio'),
            'zero_ratio': model_meta.get('zero_ratio'),
            'outliers_nullified': model_meta.get('outliers_nullified'),
            'stockout_days_nullified': model_meta.get('stockout_days_nullified'),
        }
        data_quality = {
            'training_rows': training_rows,
            'date_range': {'start': train_start.isoformat(), 'end': train_end.isoformat()},
            'last_actual_date': forecast_result.get('last_actual_date') or train_end.isoformat(),
            'data_days': model_meta.get('data_days'),
            'zero_ratio': model_meta.get('zero_ratio'),
            'outliers_nullified': model_meta.get('outliers_nullified'),
            'stockout_days_nullified': model_meta.get('stockout_days_nullified'),
        }

        now = datetime.now(timezone.utc).isoformat()
        run_payload = {
            'store_id': self.store_id,
            'forecast_type': 'inventory',
            'horizon_label': horizon_label,
            'horizon_days': horizon_days,
            'granularity': horizon_label,
            'model_name': 'prophet',
            'model_version': 'inventory-prophet-v1',
            'feature_version': 'inventory-prophet-backend-v2',
            'train_start_date': train_start.isoformat(),
            'train_end_date': train_end.isoformat(),
            'predict_start_date': predict_start,
            'predict_end_date': predict_end,
            'metrics': json.dumps(metrics),
            'summary': json.dumps(summary),
            'data_quality': json.dumps(data_quality),
            'status': 'success',
            'started_at': now,
            'finished_at': now,
        }
        run_response = self._backend_post('forecast-runs', run_payload)
        run_id = self._parse_run_id(run_response)
        if not run_id:
            raise RuntimeError(f'Backend Golang berhasil dipanggil tapi run_id tidak ditemukan: {run_response}')

        confidence_level = model_meta.get('confidence_level', 0)
        results = []
        for item in forecast_array:
            target_date = self._forecast_item_target_date(item, horizon_label)
            results.append({
                'target_date': target_date,
                'predicted_value': float(item.get('predicted_usage') or 0.0),
                'lower_bound': float(item['lower_bound']) if item.get('lower_bound') is not None else None,
                'upper_bound': float(item['upper_bound']) if item.get('upper_bound') is not None else None,
                'confidence_level': int(confidence_level or 0),
                'item_id': self.ingredient_id,
                'item_type': 'ingredient',
            })

        results_response = self._backend_post('forecast-results', {'run_id': run_id, 'results': results})
        return {
            'run_id': run_id,
            'saved_results': len(results),
            'horizon_label': horizon_label,
            'horizon_days': horizon_days,
            'predict_start_date': predict_start,
            'predict_end_date': predict_end,
            'metrics': metrics,
            'summary': summary,
            'backend_run_response': run_response,
            'backend_results_response': results_response,
        }

    def save_all_forecasts(self, periods=4, freq='W', start_date=None):
        """Legacy wrapper untuk kompatibilitas route lama."""
        try:
            result = self.predict(periods=periods, freq=freq, start_date=start_date)
            self.save_forecast_result(result)
            return True
        except Exception as e:
            print(f"[ERROR] Gagal save forecast inventory: {e}")
            return False
