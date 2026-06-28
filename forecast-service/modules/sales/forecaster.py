from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
import os
import httpx
import requests
import asyncio
import logging
import psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np
import holidays
import json
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Any, Optional
from pydantic import BaseModel, Field
from config import Config
from modules.sales.trainer import trainer
logger = logging.getLogger('sales_forecaster')
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'))
    logger.addHandler(ch)

class DailyForecast(BaseModel):
    date: date
    predicted_omzet: int = Field(..., description='Prediksi jumlah omzet')
    lower_bound: int = Field(..., description='Batas bawah prediksi (confidence interval)')
    upper_bound: int = Field(..., description='Batas atas prediksi (confidence interval)')
    day_of_week: str = Field(..., description='Nama hari (Senin, Selasa, dst)')
    is_weekend: bool

class WeeklyForecast(BaseModel):
    period_start: date
    period_end: date
    predicted_omzet: int
    lower_bound: int
    upper_bound: int
    week_of_year: int
    year: int

class MonthlyForecast(BaseModel):
    period_start: date
    period_end: date
    predicted_omzet: int
    lower_bound: int
    upper_bound: int
    month: int
    year: int

class ModelMetadata(BaseModel):
    trained_at: Optional[datetime]
    training_data_points: int
    feature_importance: dict
    cv_mae: Optional[float] = Field(None, description='Legacy MAE; sama dengan MAE horizon aktif')
    cv_rmse: Optional[float] = Field(None, description='Legacy RMSE; sama dengan RMSE horizon aktif')
    horizon_method: Optional[str] = None
    metric_horizon: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    model_config = {'extra': 'allow', 'protected_namespaces': ()}

class ForecastResponse(BaseModel):
    store_id: str
    generated_at: datetime
    forecast_horizon_days: int
    forecast_start_date: Optional[date] = None
    forecast_end_date: Optional[date] = None
    start_date_source: Optional[str] = None
    last_actual_date: Optional[date] = None
    business_cutoff_rule: Optional[str] = None
    forecasts: List[DailyForecast]
    model_metadata: ModelMetadata
    status: str = 'success'
    message: str = ''
    model_config = {'protected_namespaces': ()}

class WeeklyForecastResponse(BaseModel):
    store_id: str
    generated_at: datetime
    forecast_horizon_weeks: int
    forecast_start_date: Optional[date] = None
    forecast_end_date: Optional[date] = None
    start_date_source: Optional[str] = None
    last_actual_date: Optional[date] = None
    business_cutoff_rule: Optional[str] = None
    forecasts: List[WeeklyForecast]
    model_metadata: ModelMetadata
    status: str = 'success'
    message: str = ''
    model_config = {'protected_namespaces': ()}

class MonthlyForecastResponse(BaseModel):
    store_id: str
    generated_at: datetime
    forecast_horizon_months: int
    forecast_start_date: Optional[date] = None
    forecast_end_date: Optional[date] = None
    start_date_source: Optional[str] = None
    last_actual_date: Optional[date] = None
    business_cutoff_rule: Optional[str] = None
    forecasts: List[MonthlyForecast]
    model_metadata: ModelMetadata
    status: str = 'success'
    message: str = ''
    model_config = {'protected_namespaces': ()}

class RetrainResponse(BaseModel):
    store_id: str
    status: str
    message: str
    training_data_points: int
    cv_mae: float
    cv_rmse: float
    trained_at: datetime
    feature_importance: dict

class GolangAPIClient:

    def __init__(self):
        # Samakan dengan visitors: pakai backend internal forecast route yang
        # dilindungi X-Service-Key, bukan endpoint frontend/user API.
        self.base_url = getattr(
            Config,
            'GOLANG_INTERNAL_API_BASE_URL',
            Config.GOLANG_API_BASE_URL,
        ).rstrip('/')
        self.timeout = httpx.Timeout(45.0, connect=10.0, read=45.0, write=10.0, pool=10.0)
        self.long_timeout = httpx.Timeout(120.0, connect=10.0, read=120.0, write=10.0, pool=10.0)

    def _extract_items(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ('data', 'items', 'results'):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _same_store(self, item: Dict[str, Any], store_id: str) -> bool:
        value = item.get('m_store_id') or item.get('store_id') or item.get('storeId') or item.get('mStoreId')
        return str(value) == str(store_id)

    def _headers(self) -> Dict[str, str]:
        return Config.backend_headers()

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        *,
        timeout: Optional[httpx.Timeout] = None,
        attempts: int = 3,
    ) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        attempts = max(1, attempts)
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                    response = await client.get(url, params=params, headers=self._headers())
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f'HTTP error {e.response.status_code} on {url}: {e.response.text}')
                raise
            except httpx.RequestError as e:
                logger.warning(f'Request error attempt {attempt + 1}/{attempts} on {url}: {e}')
                if attempt < attempts - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def _post(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        *,
        timeout: Optional[httpx.Timeout] = None,
        attempts: int = 2,
    ) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        attempts = max(1, attempts)
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout or self.long_timeout) as client:
                    response = await client.post(url, json=payload, headers=self._headers())
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                body = e.response.text
                logger.error(f'HTTP error {e.response.status_code} on POST {url}: {body}')
                raise RuntimeError(f'Backend Golang menolak save forecast sales ({e.response.status_code}): {body}') from e
            except httpx.RequestError as e:
                logger.warning(f'Request error attempt {attempt + 1}/{attempts} on POST {url}: {e}')
                if attempt < attempts - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f'Gagal menghubungi backend Golang saat save forecast sales: {e}') from e

    async def fetch_sales_daily_summaries(self, store_id: str) -> List[Dict]:
        logger.info(f'Fetching sales daily summaries for store {store_id}')
        data = await self._get('sales-daily-summaries', params={'store_id': store_id}, timeout=self.long_timeout, attempts=2)
        items = self._extract_items(data)
        filtered = [item for item in items if self._same_store(item, store_id)]
        return filtered or items

    async def fetch_sales_monthly_summaries(self, store_id: str) -> List[Dict]:
        logger.info(f'Fetching sales monthly summaries for store {store_id}')
        data = await self._get('sales-monthly-summaries', params={'store_id': store_id}, timeout=self.long_timeout, attempts=2)
        items = self._extract_items(data)
        filtered = [item for item in items if self._same_store(item, store_id)]
        return filtered or items

    async def fetch_orders(self, store_id: str) -> List[Dict]:
        logger.info(f'Fetching orders for store {store_id}')
        data = await self._get('orders', params={'store_id': store_id}, timeout=self.long_timeout, attempts=2)
        items = self._extract_items(data)
        filtered = [item for item in items if self._same_store(item, store_id)]
        return filtered or items

    async def fetch_store_operational_hours(self, store_id: str) -> List[Dict]:
        logger.info(f'Fetching operational hours for store {store_id}')
        try:
            data = await self._get('store-operational-hours', params={'store_id': store_id}, timeout=self.timeout, attempts=2)
            items = self._extract_items(data)
            filtered = [item for item in items if self._same_store(item, store_id)]
            return filtered or items
        except Exception as exc:
            logger.warning(f'Failed to fetch operational hours via backend API, fallback open 24h: {exc}')
            return []

    async def fetch_all_historical_data(self, store_id: str) -> Dict[str, List[Dict]]:
        logger.info(f'Fetching all historical data for store {store_id}')
        daily_task = self.fetch_sales_daily_summaries(store_id)
        monthly_task = self.fetch_sales_monthly_summaries(store_id)
        orders_task = self.fetch_orders(store_id)
        ops_task = self.fetch_store_operational_hours(store_id)
        daily, monthly, orders, ops = await asyncio.gather(daily_task, monthly_task, orders_task, ops_task)
        return {'sales_daily': daily, 'sales_monthly': monthly, 'orders': orders, 'operational_hours': ops}

    async def save_sales_forecast(
        self,
        *,
        store_id: str,
        horizon_label: str,
        horizon_days: int,
        result_rows: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        summary: Dict[str, Any],
        data_quality: Dict[str, Any],
        train_start_date: date,
        train_end_date: date,
        predict_start_date: date,
        predict_end_date: date,
        model_version: str,
    ) -> Dict[str, Any]:
        if not result_rows:
            raise ValueError('result_rows kosong, tidak ada data forecast untuk disimpan.')

        now = datetime.now(timezone.utc).isoformat()
        run_payload = {
            'store_id': store_id,
            'forecast_type': 'sales',
            'horizon_label': horizon_label,
            'horizon_days': horizon_days,
            'granularity': horizon_label,
            'model_name': 'random forest',
            'model_version': model_version,
            'feature_version': 'sales-backend-v2',
            'train_start_date': train_start_date.isoformat(),
            'train_end_date': train_end_date.isoformat(),
            'predict_start_date': predict_start_date.isoformat(),
            'predict_end_date': predict_end_date.isoformat(),
            'metrics': json.dumps(metrics),
            'summary': json.dumps(summary),
            'data_quality': json.dumps(data_quality),
            'status': 'success',
            'started_at': now,
            'finished_at': now,
        }

        run_response = await self._post('forecast-runs', run_payload, timeout=self.long_timeout)
        run_id = (
            run_response.get('run_id')
            or (run_response.get('data') or {}).get('run_id')
            or (run_response.get('data') or {}).get('id')
            or run_response.get('id')
        )
        if not run_id:
            raise RuntimeError(f'Backend Golang berhasil dipanggil tapi run_id tidak ditemukan: {run_response}')

        results_payload = {
            'run_id': run_id,
            'results': [
                {
                    'target_date': row['target_date'].isoformat() if hasattr(row['target_date'], 'isoformat') else row['target_date'],
                    'predicted_value': float(row['predicted_value']),
                    'lower_bound': float(row['lower_bound']) if row.get('lower_bound') is not None else None,
                    'upper_bound': float(row['upper_bound']) if row.get('upper_bound') is not None else None,
                    'confidence_level': row.get('confidence_level'),
                    'item_id': None,
                    'item_type': 'sales',
                }
                for row in result_rows
            ],
        }
        results_response = await self._post('forecast-results', results_payload, timeout=self.long_timeout)

        return {
            'run_id': int(run_id),
            'saved_results': len(result_rows),
            'horizon_label': horizon_label,
            'horizon_days': horizon_days,
            'predict_start_date': predict_start_date.isoformat(),
            'predict_end_date': predict_end_date.isoformat(),
            'backend_run_response': run_response,
            'backend_results_response': results_response,
        }

golang_client = GolangAPIClient()

class PostgresClient:

    def __init__(self) -> None:
        pass

    def _connect(self):
        return psycopg2.connect(host=os.getenv('DB_HOST', ''), port=os.getenv('DB_PORT', ''), user=os.getenv('DB_USER', ''), password=os.getenv('DB_PASSWORD', ''), dbname=os.getenv('DB_NAME', ''), sslmode=os.getenv('DB_SSLMODE', 'disable'))

    def fetch_sales_daily_summaries(self, store_id: str) -> List[Dict[str, Any]]:
        sql = '\n            SELECT date, total_transaction, total_omzet\n            FROM t_sales_daily_summaries\n            WHERE m_store_id = %s AND deleted_at IS NULL\n            ORDER BY date ASC\n        '
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f'DB error fetch_sales_daily_summaries: {exc}')
            return []

    def fetch_orders(self, store_id: str) -> List[Dict[str, Any]]:
        sql = '\n            SELECT id, created_at, total_price\n            FROM t_orders\n            WHERE m_store_id = %s AND deleted_at IS NULL\n            ORDER BY created_at ASC\n        '
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f'DB error fetch_orders: {exc}')
            return []

    def get_training_range(self, store_id: str) -> Tuple[date, date, int]:
        sql = "SELECT MIN(date), MAX(date), COUNT(*) FROM t_sales_daily_summaries WHERE m_store_id = %s AND deleted_at IS NULL"
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (store_id,))
                    res = cur.fetchone()
                    if res and res[0]:
                        return res[0], res[1], res[2]
        except Exception as exc:
            logger.error(f'DB error get_training_range: {exc}')
        
        today = date.today()
        return today, today, 0


    def save_sales_forecast(
        self,
        *,
        store_id: str,
        horizon_label: str,
        horizon_days: int,
        result_rows: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        summary: Dict[str, Any],
        data_quality: Dict[str, Any],
        train_start_date: date,
        train_end_date: date,
        predict_start_date: date,
        predict_end_date: date,
        model_version: str,
    ) -> Dict[str, Any]:
        if not result_rows:
            raise ValueError("result_rows kosong, tidak ada data forecast untuk disimpan.")

        now = datetime.now(timezone.utc)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE forecast_runs
                    SET is_latest = false
                    WHERE store_id = %s
                      AND forecast_type = 'sales'
                      AND horizon_label = %s
                    """,
                    (store_id, horizon_label),
                )

                cur.execute(
                    """
                    INSERT INTO forecast_runs (
                        store_id, forecast_type, horizon_label, horizon_days,
                        granularity, model_name, model_version, feature_version,
                        train_start_date, train_end_date, predict_start_date, predict_end_date,
                        metrics, summary, data_quality, status, is_latest,
                        started_at, finished_at
                    ) VALUES (
                        %s, 'sales', %s, %s,
                        %s, 'random forest', %s, 'sales-backend-v2',
                        %s, %s, %s, %s,
                        %s, %s, %s, 'success', true,
                        %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        store_id,
                        horizon_label,
                        horizon_days,
                        horizon_label,
                        model_version,
                        train_start_date,
                        train_end_date,
                        predict_start_date,
                        predict_end_date,
                        psycopg2.extras.Json(metrics),
                        psycopg2.extras.Json(summary),
                        psycopg2.extras.Json(data_quality),
                        now,
                        now,
                    ),
                )
                run_id = cur.fetchone()[0]

                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO forecast_results (
                        run_id, target_date, predicted_value, lower_bound,
                        upper_bound, confidence_level, item_id, item_type
                    ) VALUES %s
                    """,
                    [
                        (
                            run_id,
                            row["target_date"],
                            row["predicted_value"],
                            row.get("lower_bound"),
                            row.get("upper_bound"),
                            row.get("confidence_level"),
                            None,
                            "sales",
                        )
                        for row in result_rows
                    ],
                )
            conn.commit()

        return {"run_id": run_id}

    def fetch_all_historical_data(self, store_id: str) -> Dict[str, List[Dict[str, Any]]]:
        daily = self.fetch_sales_daily_summaries(store_id)
        orders = self.fetch_orders(store_id)
        return {'sales_daily': daily, 'sales_monthly': [], 'orders': orders, 'operational_hours': []}
db_client = PostgresClient()
HARI_INDONESIA = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}

class SalesPreprocessor:

    def _seconds_from_time_like(self, value: Any) -> Optional[int]:
        if value is None or pd.isna(value):
            return None
        ts = pd.to_datetime(value, errors="coerce")
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

    def _parse_operational_hours(self, records: List[Dict]) -> Dict[int, Dict[str, float]]:
        op_map: Dict[int, Dict[str, float]] = {}
        for record in records or []:
            try:
                day_key = int(record.get("day_of_week", record.get("dayOfWeek")))
            except Exception:
                continue
            is_active = bool(record.get("is_active", record.get("isActive", False)))
            duration = self._calculate_open_duration_hours(
                is_active=is_active,
                open_time=record.get("open_time", record.get("openTime")),
                close_time=record.get("close_time", record.get("closeTime")),
            )
            op_map[day_key] = {
                "is_store_open": 1.0 if is_active and duration > 0 else 0.0,
                "open_duration_hours": duration,
                "is_24_hours": 1.0 if is_active and duration >= 23.99 else 0.0,
            }
        return op_map

    def _operational_features_for_date(
        self,
        target_date: pd.Timestamp,
        op_map: Optional[Dict[int, Dict[str, float]]] = None,
    ) -> Dict[str, float]:
        if not op_map:
            return {
                "is_store_open": 1.0,
                "open_duration_hours": 24.0,
                "is_24_hours": 1.0,
            }

        candidates = [int(target_date.dayofweek), int(target_date.dayofweek) + 1, int(target_date.isoweekday())]
        for key in candidates:
            if key in op_map:
                return op_map[key]

        return {
            "is_store_open": 1.0,
            "open_duration_hours": 24.0,
            "is_24_hours": 1.0,
        }

    def _apply_operational_hours(self, df: pd.DataFrame, records: List[Dict]) -> pd.DataFrame:
        df = df.copy()
        op_map = self._parse_operational_hours(records)
        dates = pd.to_datetime(df["date"])
        features = [self._operational_features_for_date(ts, op_map) for ts in dates]
        op_df = pd.DataFrame(features)
        for col in ["is_store_open", "open_duration_hours", "is_24_hours"]:
            df[col] = pd.to_numeric(op_df[col], errors="coerce").fillna(0.0)
        return df

    def _complete_daily_range(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        start_date = df['date'].min()
        end_date = df['date'].max()
        full_dates = pd.DataFrame({'date': pd.date_range(start_date, end_date, freq='D')})
        merged = full_dates.merge(df, on='date', how='left')
        numeric_cols = [c for c in merged.columns if c != 'date']
        for col in numeric_cols:
            merged[col] = pd.to_numeric(merged[col], errors='coerce').fillna(0)
        merged['date'] = merged['date'].dt.date
        return merged

    def build_daily_dataframe(self, raw_data: Dict[str, List[Dict]]) -> pd.DataFrame:
        df = self._build_from_sales_daily(raw_data.get('sales_daily', []))
        if df.empty:
            logger.warning('sales_daily kosong, fallback ke data orders')
            df = self._build_from_orders(raw_data.get('orders', []))
        if df.empty:
            logger.error('Tidak ada data historis yang bisa digunakan')
            return pd.DataFrame()
        df = self._complete_daily_range(df)
        df = self._apply_operational_hours(df, raw_data.get('operational_hours', []))
        df = df.sort_values('date').reset_index(drop=True)
        return df

    def build_weekly_dataframe(self, raw_data: Dict[str, List[Dict]]) -> pd.DataFrame:
        df_daily = self.build_daily_dataframe(raw_data)
        if df_daily.empty:
            return pd.DataFrame()
        df_daily = df_daily.copy()
        df_daily['date'] = pd.to_datetime(df_daily['date'])
        df_daily = df_daily.set_index('date').sort_index()
        weekly = df_daily.resample('W-SUN').sum(numeric_only=True)
        weekly = weekly.reset_index().rename(columns={'date': 'period_end'})
        weekly['date'] = weekly['period_end'] - pd.Timedelta(days=6)
        return weekly[['date', 'omzet']].copy()

    def build_monthly_dataframe(self, raw_data: Dict[str, List[Dict]]) -> pd.DataFrame:
        df_daily = self.build_daily_dataframe(raw_data)
        if df_daily.empty:
            return pd.DataFrame()
        df_daily = df_daily.copy()
        df_daily['date'] = pd.to_datetime(df_daily['date'])
        df_daily = df_daily.set_index('date').sort_index()
        monthly = df_daily.resample('MS').sum(numeric_only=True)
        monthly = monthly.reset_index()
        return monthly[['date', 'omzet']].copy()

    def _build_from_sales_daily(self, records: List[Dict]) -> pd.DataFrame:
        if not records:
            return pd.DataFrame()
        try:
            df = pd.DataFrame(records)
            df['date'] = pd.to_datetime(df['date']).dt.date
            df['total_omzet'] = pd.to_numeric(df.get('total_omzet', df.get('totalOmzet', 0)), errors='coerce').fillna(0).clip(lower=0)
            df['total_discount'] = pd.to_numeric(df.get('total_discount', df.get('totalDiscount', 0)), errors='coerce').fillna(0).clip(lower=0)
            return df[['date', 'total_omzet', 'total_discount']].rename(columns={'total_omzet': 'omzet', 'total_discount': 'discount'})
        except Exception as e:
            logger.error(f'Error parsing sales_daily: {e}')
            return pd.DataFrame()

    def _build_from_orders(self, records: List[Dict]) -> pd.DataFrame:
        if not records:
            return pd.DataFrame()
        try:
            df = pd.DataFrame(records)
            date_col = next((c for c in ['created_at', 'createdAt', 'date'] if c in df.columns), None)
            if not date_col:
                return pd.DataFrame()
            df['date'] = pd.to_datetime(df[date_col]).dt.date
            df['total_price'] = pd.to_numeric(df.get('total_price', df.get('totalPrice', 0)), errors='coerce').fillna(0).clip(lower=0)
            df['total_discount'] = pd.to_numeric(df.get('total_discount', df.get('totalDiscount', 0)), errors='coerce').fillna(0).clip(lower=0)
            daily = df.groupby('date').agg(
                omzet=('total_price', 'sum'),
                discount=('total_discount', 'sum')
            ).reset_index()
            return daily
        except Exception as e:
            logger.error(f'Error parsing orders: {e}')
            return pd.DataFrame()

    def engineer_features(self, df: pd.DataFrame, lags: List[int] | None=None, windows: List[int] | None=None, expanding_min_periods: int | None=None) -> pd.DataFrame:
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        lags = lags or [1, 2, 3, 7, 14, 21, 28]
        windows = windows or [7, 14, 28]
        max_lag = max(lags)
        expanding_min_periods = expanding_min_periods or max(7, min(windows))
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['month'] = df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        df['week_of_year'] = df['date'].dt.isocalendar().week.astype(int)
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['is_month_start'] = df['date'].dt.is_month_start.astype(int)
        df['is_month_end'] = df['date'].dt.is_month_end.astype(int)
        
        id_holidays = holidays.ID()
        df['is_national_holiday'] = df['date'].apply(lambda d: 1.0 if d in id_holidays else 0.0)
        
        if 'discount' not in df.columns:
            df['discount'] = 0.0
        df['discount_ratio'] = np.where((df['omzet'] + df['discount']) > 0, df['discount'] / (df['omzet'] + df['discount']), 0.0)
        
        q3 = df['omzet'].quantile(0.75)
        iqr = q3 - df['omzet'].quantile(0.25)
        upper_bound = q3 + 3 * iqr
        if upper_bound > 0:
            df['omzet'] = df['omzet'].clip(upper=upper_bound)
        if "is_store_open" not in df.columns:
            df["is_store_open"] = 1.0
        if "open_duration_hours" not in df.columns:
            df["open_duration_hours"] = 24.0
        if "is_24_hours" not in df.columns:
            df["is_24_hours"] = (df["open_duration_hours"] >= 23.99).astype(float)
        df['sin_dow'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['cos_dow'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        df['sin_month'] = np.sin(2 * np.pi * df['month'] / 12)
        df['cos_month'] = np.cos(2 * np.pi * df['month'] / 12)
        for lag in lags:
            df[f'lag_{lag}'] = df['omzet'].shift(lag)
        for window in windows:
            df[f'rolling_mean_{window}'] = df['omzet'].shift(1).rolling(window=window, min_periods=1).mean()
            df[f'rolling_std_{window}'] = df['omzet'].shift(1).rolling(window=window, min_periods=1).std().fillna(0)
            df[f'rolling_max_{window}'] = df['omzet'].shift(1).rolling(window=window, min_periods=1).max()
            df[f'rolling_min_{window}'] = df['omzet'].shift(1).rolling(window=window, min_periods=1).min()
        df['expanding_mean'] = df['omzet'].shift(1).expanding(min_periods=expanding_min_periods).mean()
        df = df.dropna(subset=[f'lag_{max_lag}']).reset_index(drop=True)
        return df

    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        exclude = {'date', 'omzet', 'discount'}
        return [c for c in df.columns if c not in exclude]

    def _build_future_row(self, target_date: pd.Timestamp, history: pd.DataFrame, lags: List[int] | None=None, windows: List[int] | None=None, operational_map: Optional[Dict[int, Dict[str, float]]] = None) -> Dict[str, Any]:
        row: Dict[str, Any] = {}
        lags = lags or [1, 2, 3, 7, 14, 21, 28]
        windows = windows or [7, 14, 28]
        row['day_of_week'] = target_date.dayofweek
        row['day_of_month'] = target_date.day
        row['month'] = target_date.month
        row['quarter'] = target_date.quarter
        row['week_of_year'] = target_date.isocalendar()[1]
        row['is_weekend'] = int(target_date.dayofweek in [5, 6])
        row['is_month_start'] = int(target_date.is_month_start)
        row['is_month_end'] = int(target_date.is_month_end)
        
        id_holidays = holidays.ID()
        row['is_national_holiday'] = 1.0 if target_date in id_holidays else 0.0
        row['discount_ratio'] = 0.0
        
        row.update(self._operational_features_for_date(target_date, operational_map))
        row['sin_dow'] = np.sin(2 * np.pi * row['day_of_week'] / 7)
        row['cos_dow'] = np.cos(2 * np.pi * row['day_of_week'] / 7)
        row['sin_month'] = np.sin(2 * np.pi * row['month'] / 12)
        row['cos_month'] = np.cos(2 * np.pi * row['month'] / 12)
        hist_omzet = history['omzet'].values
        for lag in lags:
            idx = len(hist_omzet) - lag
            row[f'lag_{lag}'] = float(hist_omzet[idx]) if idx >= 0 else 0.0
        for window in windows:
            recent = hist_omzet[-window:] if len(hist_omzet) >= window else hist_omzet
            row[f'rolling_mean_{window}'] = float(np.mean(recent)) if len(recent) > 0 else 0.0
            row[f'rolling_std_{window}'] = float(np.std(recent)) if len(recent) > 1 else 0.0
            row[f'rolling_max_{window}'] = float(np.max(recent)) if len(recent) > 0 else 0.0
            row[f'rolling_min_{window}'] = float(np.min(recent)) if len(recent) > 0 else 0.0
        row['expanding_mean'] = float(np.mean(hist_omzet)) if len(hist_omzet) > 0 else 0.0
        row['date'] = target_date
        return row

class SalesForecastService:

    def __init__(self):
        self.preprocessor = SalesPreprocessor()
        self.period_configs = {'weekly': {'lags': [1, 2, 3, 4, 8, 12], 'windows': [4, 8, 12], 'expanding_min_periods': 4}, 'monthly': {'lags': [1, 2, 3, 6, 12], 'windows': [3, 6, 12], 'expanding_min_periods': 3}}

    def _now_jakarta(self) -> datetime:
        return datetime.now(ZoneInfo('Asia/Jakarta'))

    def _last_actual_date_from_df(self, df_daily: pd.DataFrame) -> Optional[date]:
        if df_daily is None or df_daily.empty or 'date' not in df_daily.columns:
            return None
        dates = pd.to_datetime(df_daily['date'], errors='coerce').dropna()
        if dates.empty:
            return None
        return dates.max().date()

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
        op_map = self.preprocessor._parse_operational_hours([record])
        features = self.preprocessor._operational_features_for_date(pd.Timestamp(target_date), op_map)
        return float(features.get('is_store_open', 0.0)) > 0

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

        open_seconds = self.preprocessor._seconds_from_time_like(record.get('open_time', record.get('openTime')))
        close_seconds = self.preprocessor._seconds_from_time_like(record.get('close_time', record.get('closeTime')))
        if open_seconds is None or close_seconds is None or open_seconds == close_seconds:
            return (
                datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tzinfo=jakarta)
                + timedelta(minutes=getattr(Config, 'FORECAST_24H_RUN_SCHEDULER_MINUTES', 120))
            )

        close_day = target_date
        if close_seconds <= open_seconds:
            close_day = target_date + timedelta(days=1)
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

    def _filter_daily_to_complete_period(
        self,
        df_daily: pd.DataFrame,
        operational_hours: List[Dict[str, Any]],
        now_jakarta: Optional[datetime] = None,
    ) -> Tuple[pd.DataFrame, date]:
        latest_complete_day = self._latest_complete_day_by_operational_hours(operational_hours, now_jakarta)
        if df_daily is None or df_daily.empty or 'date' not in df_daily.columns:
            return df_daily, latest_complete_day
        filtered = df_daily.copy()
        filtered['date'] = pd.to_datetime(filtered['date'], errors='coerce')
        filtered = filtered[filtered['date'].dt.date <= latest_complete_day]
        filtered['date'] = filtered['date'].dt.date
        return filtered, latest_complete_day

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
        df_daily: pd.DataFrame,
        operational_hours: List[Dict[str, Any]],
        requested_start_date: Optional[date],
        horizon_label: str = 'daily',
    ) -> Dict[str, Any]:
        last_actual_date = self._last_actual_date_from_df(df_daily)
        if requested_start_date is not None:
            return {
                'forecast_start_date': requested_start_date,
                'start_date_source': 'manual_body',
                'last_actual_date': last_actual_date,
                'business_cutoff_rule': 'manual_start_date',
            }

        horizon_label = (horizon_label or 'daily').lower()
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

    def _forecast_item_period_dates(self, item: Any, horizon_label: str) -> Tuple[date, date]:
        if horizon_label == 'daily':
            return (item.date, item.date)
        return (item.period_start, item.period_end)

    def _response_date_bounds(self, forecasts: List[Any], horizon_label: str) -> Tuple[Optional[date], Optional[date]]:
        if not forecasts:
            return (None, None)
        period_dates = [self._forecast_item_period_dates(item, horizon_label) for item in forecasts]
        return (min((start for start, _ in period_dates)), max((end for _, end in period_dates)))

    def _round_metric(self, val: Any, decimals: int=4) -> Optional[float]:
        if val is None or pd.isna(val):
            return None
        return round(float(val), decimals)

    def _horizon_method(self, horizon_label: str) -> str:
        if horizon_label == 'daily':
            return 'direct_daily'
        return 'aggregated_from_daily'

    async def _fetch_historical_data(self, store_id: str) -> Dict[str, List[Dict]]:
        raw_data = await golang_client.fetch_all_historical_data(store_id)
        if not raw_data.get('sales_daily') and not raw_data.get('orders'):
            logger.warning(f'Backend Golang tidak mengembalikan data historis untuk store {store_id}.')
        return raw_data

    async def retrain(self, store_id: str, force: bool=False) -> RetrainResponse:
        logger.info(f'[RETRAIN] store={store_id}, force={force}')
        raw_data = await self._fetch_historical_data(store_id)
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)
        df_daily, latest_complete_day = self._filter_daily_to_complete_period(
            df_daily,
            raw_data.get('operational_hours', []),
        )
        logger.info('[RETRAIN] store=%s menggunakan data complete sampai operational_day=%s', store_id, latest_complete_day)
        if df_daily.empty:
            raise ValueError(f'Tidak ada data historis complete untuk store {store_id}.')
        if len(df_daily) < 30:
            raise ValueError(f'Data historis terlalu sedikit: {len(df_daily)} hari. Minimal 30 hari data.')
        df_features = self.preprocessor.engineer_features(df_daily)
        feature_cols = self.preprocessor.get_feature_columns(df_features)
        meta = trainer.train(df_features, feature_cols, store_id)
        return RetrainResponse(store_id=store_id, status='success', message=f"Model berhasil dilatih dengan {meta['training_data_points']} data points", training_data_points=meta['training_data_points'], cv_mae=meta['cv_mae'], cv_rmse=meta['cv_rmse'], trained_at=datetime.fromisoformat(meta['trained_at']), feature_importance=meta['top_features'])

    async def forecast(self, store_id: str, forecast_days: int, start_date: date | None=None) -> ForecastResponse:
        logger.info(f'[FORECAST] store={store_id}, days={forecast_days}, requested_start={start_date}')
        if forecast_days <= 0:
            raise ValueError('forecast_days harus lebih besar dari 0')
        if not trainer.model_exists(store_id):
            logger.info(f'Model belum ada untuk store {store_id}, auto-training...')
            await self.retrain(store_id)
        model, scaler, feature_cols, meta = trainer.load_model(store_id)
        raw_data = await self._fetch_historical_data(store_id)
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)
        df_daily, latest_complete_day = self._filter_daily_to_complete_period(
            df_daily,
            raw_data.get('operational_hours', []),
        )
        if df_daily.empty:
            raise ValueError(f'Tidak ada data historis complete untuk store {store_id}')
        start_meta = self._resolve_forecast_start_meta(
            df_daily=df_daily,
            operational_hours=raw_data.get('operational_hours', []),
            requested_start_date=start_date,
            horizon_label='daily',
        )
        resolved_start_date = start_meta['forecast_start_date']
        hist_std = float(df_daily['omzet'].std()) if len(df_daily) > 1 else 100000.0
        ci_multiplier = 1.28
        forecasts = []
        running_history = df_daily[['date', 'omzet']].copy()
        running_history['date'] = pd.to_datetime(running_history['date'])
        op_map = self.preprocessor._parse_operational_hours(raw_data.get('operational_hours', []))
        for day_offset in range(forecast_days):
            target_date = pd.Timestamp(resolved_start_date) + timedelta(days=day_offset)
            row = self.preprocessor._build_future_row(target_date, running_history, operational_map=op_map)
            X_row = np.array([[row.get(col, 0.0) for col in feature_cols]])
            X_scaled = scaler.transform(X_row)
            tree_preds = np.array([tree.predict(X_scaled)[0] for tree in model.estimators_])
            pred_mean = float(np.mean(tree_preds))
            pred_std = float(np.std(tree_preds))
            predicted_omzet = max(0, round(pred_mean))
            lower = max(0, round(pred_mean - ci_multiplier * (pred_std + hist_std * 0.15)))
            upper = max(predicted_omzet, round(pred_mean + ci_multiplier * (pred_std + hist_std * 0.15)))
            day_name = HARI_INDONESIA.get(target_date.dayofweek, '')
            is_weekend = target_date.dayofweek in [5, 6]
            forecasts.append(DailyForecast(date=target_date.date(), predicted_omzet=predicted_omzet, lower_bound=lower, upper_bound=upper, day_of_week=day_name, is_weekend=is_weekend))
            new_row = pd.DataFrame([{'date': target_date, 'omzet': float(predicted_omzet)}])
            running_history = pd.concat([running_history, new_row], ignore_index=True)
        forecast_start, forecast_end = self._response_date_bounds(forecasts, 'daily')
        return ForecastResponse(store_id=store_id, generated_at=datetime.utcnow(), forecast_horizon_days=forecast_days, forecast_start_date=forecast_start, forecast_end_date=forecast_end, start_date_source=start_meta['start_date_source'], last_actual_date=start_meta['last_actual_date'], business_cutoff_rule=start_meta['business_cutoff_rule'], forecasts=forecasts, model_metadata=self._metadata_for_response(store_id=store_id, meta=meta, horizon_label='daily', raw_data=raw_data), status='success', message=f'Berhasil memprediksi {forecast_days} hari ke depan mulai {(forecast_start.isoformat() if forecast_start else resolved_start_date.isoformat())}')

    def _get_period_config(self, granularity: str) -> Dict[str, Any]:
        if granularity not in self.period_configs:
            raise ValueError(f'Granularity tidak dikenal: {granularity}')
        return self.period_configs[granularity]

    def _align_start_date(self, start: date, granularity: str) -> pd.Timestamp:
        ts = pd.Timestamp(start)
        if granularity == 'weekly':
            return ts - pd.Timedelta(days=ts.dayofweek)
        if granularity == 'monthly':
            return ts.replace(day=1)
        return ts

    def _next_start_date(self, last_date: pd.Timestamp, granularity: str) -> pd.Timestamp:
        if granularity == 'weekly':
            days_to_add = 7 - last_date.dayofweek
            return (last_date + pd.Timedelta(days=days_to_add)).normalize()
        if granularity == 'monthly':
            return (last_date + pd.offsets.MonthBegin(1)).normalize()
        return last_date

    def _add_periods(self, start: pd.Timestamp, offset: int, granularity: str) -> pd.Timestamp:
        if granularity == 'weekly':
            return start + pd.Timedelta(weeks=offset)
        if granularity == 'monthly':
            return start + pd.DateOffset(months=offset)
        return start

    async def _retrain_periodic(self, store_id: str, granularity: str) -> Dict[str, Any]:
        raw_data = await self._fetch_historical_data(store_id)
        if granularity == 'weekly':
            df_period = self.preprocessor.build_weekly_dataframe(raw_data)
        else:
            df_period = self.preprocessor.build_monthly_dataframe(raw_data)
        if df_period.empty:
            raise ValueError(f'Tidak ada data historis untuk store {store_id}.')
        config = self._get_period_config(granularity)
        min_points = max(config['lags']) + 1
        if len(df_period) < min_points:
            raise ValueError(f'Data historis terlalu sedikit: {len(df_period)} {granularity}. Minimal {min_points} periode.')
        df_features = self.preprocessor.engineer_features(df_period, lags=config['lags'], windows=config['windows'], expanding_min_periods=config['expanding_min_periods'])
        feature_cols = self.preprocessor.get_feature_columns(df_features)
        meta = trainer.train(df_features, feature_cols, store_id, granularity=granularity)
        return meta

    async def _forecast_periodic(self, store_id: str, forecast_periods: int, start_date: date | None, granularity: str):
        if not trainer.model_exists(store_id, granularity=granularity):
            logger.info(f'Model {granularity} belum ada untuk store {store_id}, auto-training...')
            await self._retrain_periodic(store_id, granularity)
        model, scaler, feature_cols, meta = trainer.load_model(store_id, granularity=granularity)
        raw_data = await self._fetch_historical_data(store_id)
        if granularity == 'weekly':
            df_period = self.preprocessor.build_weekly_dataframe(raw_data)
        else:
            df_period = self.preprocessor.build_monthly_dataframe(raw_data)
        if df_period.empty:
            raise ValueError(f'Tidak ada data historis untuk store {store_id}')
        hist_std = float(df_period['omzet'].std()) if len(df_period) > 1 else 100000.0
        ci_multiplier = 1.28
        running_history = df_period[['date', 'omzet']].copy()
        running_history['date'] = pd.to_datetime(running_history['date'])
        if start_date:
            start = self._align_start_date(start_date, granularity)
        else:
            start = self._next_start_date(running_history['date'].max(), granularity)
        config = self._get_period_config(granularity)
        forecasts = []
        for offset in range(forecast_periods):
            target_date = self._add_periods(start, offset, granularity)
            row = self.preprocessor._build_future_row(target_date, running_history, lags=config['lags'], windows=config['windows'])
            X_row = np.array([[row.get(col, 0.0) for col in feature_cols]])
            X_scaled = scaler.transform(X_row)
            tree_preds = np.array([tree.predict(X_scaled)[0] for tree in model.estimators_])
            pred_mean = float(np.mean(tree_preds))
            pred_std = float(np.std(tree_preds))
            predicted_omzet = max(0, round(pred_mean))
            lower = max(0, round(pred_mean - ci_multiplier * (pred_std + hist_std * 0.15)))
            upper = max(predicted_omzet, round(pred_mean + ci_multiplier * (pred_std + hist_std * 0.15)))
            if granularity == 'weekly':
                forecasts.append(WeeklyForecast(period_start=target_date.date(), period_end=(target_date + timedelta(days=6)).date(), predicted_omzet=predicted_omzet, lower_bound=lower, upper_bound=upper, week_of_year=int(target_date.isocalendar()[1]), year=int(target_date.year)))
            else:
                forecasts.append(MonthlyForecast(period_start=target_date.date(), period_end=(target_date + pd.offsets.MonthEnd(0)).date(), predicted_omzet=predicted_omzet, lower_bound=lower, upper_bound=upper, month=int(target_date.month), year=int(target_date.year)))
            new_row = pd.DataFrame([{'date': target_date, 'omzet': float(predicted_omzet)}])
            running_history = pd.concat([running_history, new_row], ignore_index=True)
        return (forecasts, meta)

    def _build_weekly_from_daily_response(self, *, daily_response: ForecastResponse, forecast_weeks: int) -> List[WeeklyForecast]:
        daily_items = sorted(daily_response.forecasts, key=lambda item: item.date)
        weekly_forecasts: List[WeeklyForecast] = []
        for week_index in range(forecast_weeks):
            chunk = daily_items[week_index * 7:(week_index + 1) * 7]
            if not chunk:
                break
            period_start = chunk[0].date
            period_end = chunk[-1].date
            predicted_omzet = int(sum((item.predicted_omzet for item in chunk)))
            lower_bound = int(sum((item.lower_bound for item in chunk)))
            upper_bound = int(sum((item.upper_bound for item in chunk)))
            weekly_forecasts.append(WeeklyForecast(period_start=period_start, period_end=period_end, predicted_omzet=predicted_omzet, lower_bound=lower_bound, upper_bound=max(predicted_omzet, upper_bound), week_of_year=int(pd.Timestamp(period_start).isocalendar()[1]), year=int(period_start.year)))
        return weekly_forecasts

    def _monthly_periods(self, *, forecast_months: int, start_date: date | None) -> List[Tuple[date, date]]:
        if forecast_months <= 0:
            return []
        first_start = pd.Timestamp(start_date or self._now_jakarta().date()).normalize()
        first_month = first_start.replace(day=1).normalize()
        periods: List[Tuple[date, date]] = []
        for offset in range(forecast_months):
            if offset == 0:
                period_start = first_start
            else:
                period_start = (first_month + pd.DateOffset(months=offset)).normalize()
            period_end = (period_start + pd.offsets.MonthEnd(0)).normalize()
            periods.append((period_start.date(), period_end.date()))
        return periods

    def _build_monthly_from_daily_response(self, *, daily_response: ForecastResponse, periods: List[Tuple[date, date]]) -> List[MonthlyForecast]:
        daily_items = sorted(daily_response.forecasts, key=lambda item: item.date)
        monthly_forecasts: List[MonthlyForecast] = []
        for period_start, period_end in periods:
            chunk = [item for item in daily_items if period_start <= item.date <= period_end]
            if not chunk:
                continue
            predicted_omzet = int(sum((item.predicted_omzet for item in chunk)))
            lower_bound = int(sum((item.lower_bound for item in chunk)))
            upper_bound = int(sum((item.upper_bound for item in chunk)))
            monthly_forecasts.append(MonthlyForecast(period_start=period_start, period_end=period_end, predicted_omzet=predicted_omzet, lower_bound=lower_bound, upper_bound=max(predicted_omzet, upper_bound), month=int(period_start.month), year=int(period_start.year)))
        return monthly_forecasts

    async def forecast_weekly(self, store_id: str, forecast_weeks: int, start_date: date | None=None) -> WeeklyForecastResponse:
        if forecast_weeks <= 0:
            raise ValueError('forecast_weeks harus lebih besar dari 0')

        weekly_start_meta = None
        resolved_start_date = start_date
        if resolved_start_date is None:
            raw_data = await self._fetch_historical_data(store_id)
            df_daily = self.preprocessor.build_daily_dataframe(raw_data)
            df_daily, _ = self._filter_daily_to_complete_period(
                df_daily,
                raw_data.get('operational_hours', []),
            )
            if df_daily.empty:
                raise ValueError(f'Tidak ada data historis complete untuk store {store_id}')
            weekly_start_meta = self._resolve_forecast_start_meta(
                df_daily=df_daily,
                operational_hours=raw_data.get('operational_hours', []),
                requested_start_date=None,
                horizon_label='weekly',
            )
            resolved_start_date = weekly_start_meta['forecast_start_date']

        daily_response = await self.forecast(
            store_id=store_id,
            forecast_days=forecast_weeks * 7,
            start_date=resolved_start_date,
        )
        forecasts = self._build_weekly_from_daily_response(
            daily_response=daily_response,
            forecast_weeks=forecast_weeks,
        )
        forecast_start, forecast_end = self._response_date_bounds(forecasts, 'weekly')
        return WeeklyForecastResponse(
            store_id=store_id,
            generated_at=datetime.utcnow(),
            forecast_horizon_weeks=forecast_weeks,
            forecast_start_date=forecast_start,
            forecast_end_date=forecast_end,
            start_date_source=(weekly_start_meta['start_date_source'] if weekly_start_meta else daily_response.start_date_source),
            last_actual_date=(weekly_start_meta['last_actual_date'] if weekly_start_meta else daily_response.last_actual_date),
            business_cutoff_rule=(weekly_start_meta['business_cutoff_rule'] if weekly_start_meta else daily_response.business_cutoff_rule),
            forecasts=forecasts,
            model_metadata=self._metadata_for_response(
                store_id=store_id,
                meta=trainer.load_model(store_id)[3],
                horizon_label='weekly',
            ),
            status='success',
            message=f'Berhasil memprediksi {forecast_weeks} minggu ke depan dari agregasi daily forecast',
        )

    async def forecast_monthly(self, store_id: str, forecast_months: int, start_date: date | None=None) -> MonthlyForecastResponse:
        if forecast_months <= 0:
            raise ValueError('forecast_months harus lebih besar dari 0')
        resolved_start_date = start_date
        monthly_start_meta = None
        if resolved_start_date is None:
            raw_data = await self._fetch_historical_data(store_id)
            df_daily = self.preprocessor.build_daily_dataframe(raw_data)
            df_daily, _ = self._filter_daily_to_complete_period(
                df_daily,
                raw_data.get('operational_hours', []),
            )
            if df_daily.empty:
                raise ValueError(f'Tidak ada data historis complete untuk store {store_id}')
            monthly_start_meta = self._resolve_forecast_start_meta(
                df_daily=df_daily,
                operational_hours=raw_data.get('operational_hours', []),
                requested_start_date=None,
                horizon_label='monthly',
            )
            resolved_start_date = monthly_start_meta['forecast_start_date']

        periods = self._monthly_periods(forecast_months=forecast_months, start_date=resolved_start_date)
        if not periods:
            raise ValueError('Periode monthly forecast kosong')
        daily_start = periods[0][0]
        daily_end = periods[-1][1]
        forecast_days = (daily_end - daily_start).days + 1
        daily_response = await self.forecast(store_id=store_id, forecast_days=forecast_days, start_date=daily_start)
        forecasts = self._build_monthly_from_daily_response(daily_response=daily_response, periods=periods)
        forecast_start, forecast_end = self._response_date_bounds(forecasts, 'monthly')
        return MonthlyForecastResponse(
            store_id=store_id,
            generated_at=datetime.utcnow(),
            forecast_horizon_months=forecast_months,
            forecast_start_date=forecast_start,
            forecast_end_date=forecast_end,
            start_date_source=(monthly_start_meta['start_date_source'] if monthly_start_meta else daily_response.start_date_source),
            last_actual_date=(monthly_start_meta['last_actual_date'] if monthly_start_meta else daily_response.last_actual_date),
            business_cutoff_rule=(monthly_start_meta['business_cutoff_rule'] if monthly_start_meta else daily_response.business_cutoff_rule),
            forecasts=forecasts,
            model_metadata=self._metadata_for_response(
                store_id=store_id,
                meta=trainer.load_model(store_id)[3],
                horizon_label='monthly',
            ),
            status='success',
            message=f'Berhasil memprediksi {forecast_months} bulan ke depan dari agregasi daily forecast',
        )

    async def forecast_by_horizon(
        self,
        *,
        store_id: str,
        horizon_label: str,
        horizon_count: int,
        start_date: date | None = None,
    ):
        if horizon_count <= 0:
            raise ValueError('horizon_count harus lebih besar dari 0')
        if horizon_label == 'daily':
            return await self.forecast(store_id=store_id, forecast_days=horizon_count, start_date=start_date)
        if horizon_label == 'weekly':
            return await self.forecast_weekly(store_id=store_id, forecast_weeks=horizon_count, start_date=start_date)
        if horizon_label == 'monthly':
            return await self.forecast_monthly(store_id=store_id, forecast_months=horizon_count, start_date=start_date)
        raise ValueError('horizon_label harus daily, weekly, atau monthly')

    async def _training_range(self, store_id: str) -> Tuple[date, date, int]:
        raw_data = await self._fetch_historical_data(store_id)
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)
        df_daily, _ = self._filter_daily_to_complete_period(
            df_daily,
            raw_data.get('operational_hours', []),
        )
        if df_daily.empty:
            today = date.today()
            return today, today, 0
        dates = pd.to_datetime(df_daily['date'])
        return dates.min().date(), dates.max().date(), int(len(df_daily))

    async def save_forecast_result(
        self,
        *,
        forecast_response: ForecastResponse | WeeklyForecastResponse | MonthlyForecastResponse,
        horizon_label: str,
        horizon_count: int,
    ) -> Dict[str, Any]:
        forecasts = forecast_response.forecasts
        if not forecasts:
            raise ValueError('Forecast kosong, tidak ada data untuk disimpan.')

        period_dates = [self._forecast_item_period_dates(item, horizon_label) for item in forecasts]
        predict_start = min(start for start, _ in period_dates)
        predict_end = max(end for _, end in period_dates)
        horizon_days = (predict_end - predict_start).days + 1

        metadata = forecast_response.model_metadata
        metadata_metrics = dict(getattr(metadata, 'metrics', {}) or {})
        mae_value = metadata_metrics.get(f'{horizon_label}_mae', getattr(metadata, 'cv_mae', None))
        rmse_value = metadata_metrics.get(f'{horizon_label}_rmse', getattr(metadata, 'cv_rmse', None))
        mae = float(mae_value or 0.0)
        rmse = float(rmse_value or 0.0)
        model_version = 'sales-rf-v2-aggregated'

        avg_prediction = max(1.0, float(np.mean([max(0, item.predicted_omzet) for item in forecasts])))
        forecast_error_ratio = min(1.0, mae / avg_prediction) if mae > 0 else 0.0
        confidence_level = int(max(0, min(100, round(100.0 - forecast_error_ratio * 100.0))))

        result_rows: List[Dict[str, Any]] = []
        for item in forecasts:
            target_date = item.date if horizon_label == 'daily' else item.period_start
            result_rows.append({
                'target_date': target_date,
                'predicted_value': float(item.predicted_omzet),
                'lower_bound': float(item.lower_bound) if item.lower_bound is not None else None,
                'upper_bound': float(item.upper_bound) if item.upper_bound is not None else None,
                'confidence_level': confidence_level,
            })

        train_start, train_end, raw_train_rows = await self._training_range(forecast_response.store_id)

        metrics = {
            'horizon_method': getattr(metadata, 'horizon_method', None),
            'metric_horizon': horizon_label,
            'mae': mae,
            'rmse': rmse,
            'mape': None,
            'confidence_level': confidence_level,
            'forecast_error_ratio': round(forecast_error_ratio, 4),
            f'{horizon_label}_mae': mae,
            f'{horizon_label}_rmse': rmse,
            f'{horizon_label}_mae_percentage': metadata_metrics.get(f'{horizon_label}_mae_percentage'),
            f'{horizon_label}_error_ratio': metadata_metrics.get(f'{horizon_label}_error_ratio'),
            f'{horizon_label}_wape': metadata_metrics.get(f'{horizon_label}_wape'),
            f'{horizon_label}_error_percentage': metadata_metrics.get(f'{horizon_label}_error_percentage'),
            f'{horizon_label}_bias': metadata_metrics.get(f'{horizon_label}_bias'),
            f'{horizon_label}_mean_error': metadata_metrics.get(f'{horizon_label}_mean_error'),
            f'{horizon_label}_bias_percentage': metadata_metrics.get(f'{horizon_label}_bias_percentage'),
            f'{horizon_label}_interval_coverage': metadata_metrics.get(f'{horizon_label}_interval_coverage'),
            f'{horizon_label}_avg_interval_width': metadata_metrics.get(f'{horizon_label}_avg_interval_width'),
            f'{horizon_label}_relative_interval_width': metadata_metrics.get(f'{horizon_label}_relative_interval_width'),
            f'{horizon_label}_reliability': metadata_metrics.get(f'{horizon_label}_reliability'),
        }
        summary = {
            'module': 'sales',
            'horizon_label': horizon_label,
            'horizon_count': horizon_count,
            'horizon_days': horizon_days,
            'forecast_start_date': predict_start.isoformat(),
            'forecast_end_date': predict_end.isoformat(),
            'start_date_source': getattr(forecast_response, 'start_date_source', None),
            'last_actual_date': (forecast_response.last_actual_date.isoformat() if getattr(forecast_response, 'last_actual_date', None) else None),
            'business_cutoff_rule': getattr(forecast_response, 'business_cutoff_rule', None),
            'prediction_count': len(result_rows),
            'total_predicted_omzet': int(sum(row['predicted_value'] for row in result_rows)),
            'average_predicted_omzet': round(avg_prediction, 2),
            'generated_at': forecast_response.generated_at.isoformat(),
        }
        data_quality = {
            'training_rows': raw_train_rows,
            'model_training_data_points': metadata.training_data_points,
            'last_actual_date': (
                forecast_response.last_actual_date.isoformat()
                if getattr(forecast_response, 'last_actual_date', None)
                else train_end.isoformat()
            ),
            'date_range': {'start': train_start.isoformat(), 'end': train_end.isoformat()},
        }

        save_result = await golang_client.save_sales_forecast(
            store_id=forecast_response.store_id,
            horizon_label=horizon_label,
            horizon_days=horizon_days,
            result_rows=result_rows,
            metrics=metrics,
            summary=summary,
            data_quality=data_quality,
            train_start_date=train_start,
            train_end_date=train_end,
            predict_start_date=predict_start,
            predict_end_date=predict_end,
            model_version=model_version,
        )
        save_result['metrics'] = metrics
        save_result['summary'] = summary
        return save_result

    async def save_forecast_to_db(self, store_id: str, forecast_response: dict, backend_token: str=None) -> Tuple[bool, str]:
        """Legacy wrapper.

        Dipertahankan agar caller lama tidak pecah, tetapi jalur save-nya sudah
        disamakan dengan visitors: POST ke backend internal forecast-runs dan
        forecast-results memakai X-Service-Key dari Config.backend_headers().
        """
        try:
            horizon_label = forecast_response.get('request_meta', {}).get('horizon_label') or forecast_response.get('horizon', {}).get('label', 'daily')
            horizon_count = int(forecast_response.get('request_meta', {}).get('horizon_count') or forecast_response.get('horizon', {}).get('count') or 1)
            results_list = forecast_response.get('forecasts') or []
            if not results_list:
                return (False, 'Tidak ada data forecast untuk disimpan.')

            metadata = forecast_response.get('model_metadata') or {}
            metadata_metrics = metadata.get('metrics') or {}
            mae = float(metadata_metrics.get(f'{horizon_label}_mae') or metadata.get('cv_mae') or 0.0)
            rmse = float(metadata_metrics.get(f'{horizon_label}_rmse') or metadata.get('cv_rmse') or 0.0)
            avg_prediction = max(1.0, float(np.mean([max(0, item.get('predicted_omzet', 0)) for item in results_list])))
            forecast_error_ratio = min(1.0, mae / avg_prediction) if mae > 0 else 0.0
            confidence_level = int(max(0, min(100, round(100.0 - forecast_error_ratio * 100.0))))

            result_rows = []
            period_bounds = []
            for item in results_list:
                start_raw = item.get('date') or item.get('period_start')
                end_raw = item.get('date') or item.get('period_end') or item.get('period_start')
                start_dt = pd.to_datetime(start_raw).date()
                end_dt = pd.to_datetime(end_raw).date()
                period_bounds.append((start_dt, end_dt))
                result_rows.append({
                    'target_date': start_dt,
                    'predicted_value': float(item.get('predicted_omzet') or 0.0),
                    'lower_bound': float(item['lower_bound']) if item.get('lower_bound') is not None else None,
                    'upper_bound': float(item['upper_bound']) if item.get('upper_bound') is not None else None,
                    'confidence_level': confidence_level,
                })

            predict_start = min(start for start, _ in period_bounds)
            predict_end = max(end for _, end in period_bounds)
            horizon_days = (predict_end - predict_start).days + 1
            train_start, train_end, train_rows = await self._training_range(store_id)
            generated_at = forecast_response.get('generated_at') or datetime.now(timezone.utc).isoformat()
            last_actual = forecast_response.get('last_actual_date')
            last_actual_str = last_actual.isoformat() if hasattr(last_actual, 'isoformat') else str(last_actual) if last_actual else None

            metrics = {
                'horizon_method': metadata.get('horizon_method'),
                'metric_horizon': horizon_label,
                'mae': mae,
                'rmse': rmse,
                'mape': None,
                'confidence_level': confidence_level,
                'forecast_error_ratio': round(forecast_error_ratio, 4),
                f'{horizon_label}_mae': mae,
                f'{horizon_label}_rmse': rmse,
                f'{horizon_label}_mae_percentage': metadata_metrics.get(f'{horizon_label}_mae_percentage'),
                f'{horizon_label}_error_ratio': metadata_metrics.get(f'{horizon_label}_error_ratio'),
                f'{horizon_label}_wape': metadata_metrics.get(f'{horizon_label}_wape'),
                f'{horizon_label}_error_percentage': metadata_metrics.get(f'{horizon_label}_error_percentage'),
                f'{horizon_label}_reliability': metadata_metrics.get(f'{horizon_label}_reliability'),
            }
            summary = {
                'module': 'sales',
                'horizon_label': horizon_label,
                'horizon_count': horizon_count,
                'horizon_days': horizon_days,
                'forecast_start_date': predict_start.isoformat(),
                'forecast_end_date': predict_end.isoformat(),
                'start_date_source': forecast_response.get('start_date_source'),
                'last_actual_date': last_actual_str,
                'business_cutoff_rule': forecast_response.get('business_cutoff_rule'),
                'prediction_count': len(result_rows),
                'total_predicted_omzet': int(sum(row['predicted_value'] for row in result_rows)),
                'average_predicted_omzet': round(avg_prediction, 2),
                'generated_at': generated_at,
            }
            data_quality = {
                'training_rows': train_rows,
                'model_training_data_points': metadata.get('training_data_points', 0),
                'last_actual_date': last_actual_str or train_end.isoformat(),
                'date_range': {'start': train_start.isoformat(), 'end': train_end.isoformat()},
            }
            save_result = await golang_client.save_sales_forecast(
                store_id=store_id,
                horizon_label=horizon_label,
                horizon_days=horizon_days,
                result_rows=result_rows,
                metrics=metrics,
                summary=summary,
                data_quality=data_quality,
                train_start_date=train_start,
                train_end_date=train_end,
                predict_start_date=predict_start,
                predict_end_date=predict_end,
                model_version='sales-rf-v2-aggregated',
            )
            return (True, f"Forecast sales berhasil disimpan ke backend internal. run_id={save_result.get('run_id')}")
        except Exception as e:
            logger.error(f"Gagal save_sales_forecast ke backend internal: {e}")
            return (False, f'Gagal simpan ke backend internal: {e}')


    def _empty_metric_block(self, prefix: str) -> Dict[str, Any]:
        return {f'{prefix}_metric_available': False, f'{prefix}_mae': None, f'{prefix}_rmse': None, f'{prefix}_mae_percentage': None, f'{prefix}_error_ratio': None, f'{prefix}_wape': None, f'{prefix}_error_percentage': None, f'{prefix}_bias': None, f'{prefix}_mean_error': None, f'{prefix}_bias_percentage': None, f'{prefix}_interval_coverage': None, f'{prefix}_avg_interval_width': None, f'{prefix}_relative_interval_width': None, f'{prefix}_reliability': None}

    def _classify_reliability(self, error_ratio: Optional[float]) -> Optional[str]:
        """
        error_ratio disimpan sebagai rasio 0..1.
        Batas ini sengaja sederhana agar mudah ditampilkan di frontend.
        """
        if error_ratio is None:
            return None
        if error_ratio <= 0.1:
            return 'high'
        if error_ratio <= 0.2:
            return 'medium'
        if error_ratio <= 0.3:
            return 'low_medium'
        return 'low'

    def _metric_block(self, prefix: str, actual: np.ndarray, predicted: np.ndarray, lower_bound: Optional[np.ndarray]=None, upper_bound: Optional[np.ndarray]=None) -> Dict[str, Any]:
        actual = np.asarray(actual, dtype=float)
        predicted = np.asarray(predicted, dtype=float)
        if len(actual) == 0 or len(predicted) == 0:
            return self._empty_metric_block(prefix)
        mae = float(mean_absolute_error(actual, predicted))
        rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
        total_actual = float(np.sum(np.abs(actual)))
        if total_actual <= 0:
            wape = None
            error_percentage = None
        else:
            wape = float(np.sum(np.abs(actual - predicted)) / total_actual)
            error_percentage = wape * 100.0
        error_ratio = wape
        mae_percentage = error_percentage
        mean_error = float(np.mean(predicted - actual))
        avg_actual = float(np.mean(np.abs(actual)))
        if avg_actual <= 0:
            bias_percentage = None
        else:
            bias_percentage = mean_error / avg_actual * 100.0
        interval_coverage = None
        avg_interval_width = None
        relative_interval_width = None
        if lower_bound is not None and upper_bound is not None:
            lower = np.asarray(lower_bound, dtype=float)
            upper = np.asarray(upper_bound, dtype=float)
            if len(lower) == len(actual) and len(upper) == len(actual) and (len(lower) > 0):
                interval_coverage = float(np.mean((actual >= lower) & (actual <= upper)))
                widths = np.maximum(0.0, upper - lower)
                avg_interval_width = float(np.mean(widths))
                avg_predicted = float(np.mean(np.abs(predicted)))
                if avg_predicted > 0:
                    relative_interval_width = avg_interval_width / avg_predicted
        return {f'{prefix}_metric_available': True, f'{prefix}_mae': self._round_metric(mae), f'{prefix}_rmse': self._round_metric(rmse), f'{prefix}_mae_percentage': self._round_metric(mae_percentage, 2), f'{prefix}_error_ratio': self._round_metric(error_ratio, 4), f'{prefix}_wape': self._round_metric(wape, 4), f'{prefix}_error_percentage': self._round_metric(error_percentage, 2), f'{prefix}_bias': self._round_metric(mean_error), f'{prefix}_mean_error': self._round_metric(mean_error), f'{prefix}_bias_percentage': self._round_metric(bias_percentage, 2), f'{prefix}_interval_coverage': self._round_metric(interval_coverage, 4), f'{prefix}_avg_interval_width': self._round_metric(avg_interval_width), f'{prefix}_relative_interval_width': self._round_metric(relative_interval_width, 4), f'{prefix}_reliability': self._classify_reliability(error_ratio)}

    def _aggregate_oos_metric(self, oos_df: pd.DataFrame, horizon: str) -> Dict[str, Any]:
        if oos_df.empty:
            return self._metric_block(horizon, np.array([]), np.array([]))
        df = oos_df.copy()
        df['date'] = pd.to_datetime(df['date'])
        if horizon == 'weekly':
            df['period_start'] = df['date'].dt.to_period('W-SUN').apply(lambda p: p.start_time.date())
            agg_spec = {'actual': ('actual', 'sum'), 'predicted': ('predicted', 'sum'), 'days': ('date', 'count')}
            if 'lower_bound' in df.columns and 'upper_bound' in df.columns:
                agg_spec['lower_bound'] = ('lower_bound', 'sum')
                agg_spec['upper_bound'] = ('upper_bound', 'sum')
            grouped = df.groupby('period_start').agg(**agg_spec).reset_index()
            grouped = grouped[grouped['days'] >= 7]
            return self._metric_block('weekly', grouped['actual'].values, grouped['predicted'].values, grouped['lower_bound'].values if 'lower_bound' in grouped.columns else None, grouped['upper_bound'].values if 'upper_bound' in grouped.columns else None)
        if horizon == 'monthly':
            df['period'] = df['date'].dt.to_period('M')
            agg_spec = {'actual': ('actual', 'sum'), 'predicted': ('predicted', 'sum'), 'days': ('date', 'count')}
            if 'lower_bound' in df.columns and 'upper_bound' in df.columns:
                agg_spec['lower_bound'] = ('lower_bound', 'sum')
                agg_spec['upper_bound'] = ('upper_bound', 'sum')
            grouped = df.groupby('period').agg(**agg_spec).reset_index()
            grouped['expected_days'] = grouped['period'].apply(lambda p: int(p.days_in_month))
            grouped = grouped[grouped['days'] >= grouped['expected_days']]
            return self._metric_block('monthly', grouped['actual'].values, grouped['predicted'].values, grouped['lower_bound'].values if 'lower_bound' in grouped.columns else None, grouped['upper_bound'].values if 'upper_bound' in grouped.columns else None)
        return self._metric_block(horizon, np.array([]), np.array([]))

    def _build_oos_daily_predictions(self, df_features: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
        """
        Membuat out-of-sample prediction dari TimeSeriesSplit.
        Ini dipakai supaya weekly/monthly metrics dihitung dari prediksi daily historis
        yang diagregasi, bukan sekadar menyalin metric daily model.
        """
        if df_features.empty or len(df_features) < 40:
            return pd.DataFrame(columns=['date', 'actual', 'predicted', 'lower_bound', 'upper_bound'])
        X = df_features[feature_cols].values
        y = df_features['omzet'].values.astype(float)
        dates = pd.to_datetime(df_features['date'])
        n_splits = min(5, max(2, len(df_features) // 30))
        try:
            tscv = TimeSeriesSplit(n_splits=n_splits)
        except Exception:
            return pd.DataFrame(columns=['date', 'actual', 'predicted', 'lower_bound', 'upper_bound'])
        rows: List[Dict[str, Any]] = []
        for train_idx, val_idx in tscv.split(X):
            if len(train_idx) < 20 or len(val_idx) == 0:
                continue
            scaler = StandardScaler()
            X_train = scaler.fit_transform(X[train_idx])
            X_val = scaler.transform(X[val_idx])
            y_train = y[train_idx]
            y_val = y[val_idx]
            fold_model = RandomForestRegressor(n_estimators=200, max_depth=12, min_samples_split=5, min_samples_leaf=2, max_features='sqrt', bootstrap=True, random_state=42, n_jobs=-1)
            fold_model.fit(X_train, y_train)
            tree_pred_matrix = np.array([tree.predict(X_val) for tree in fold_model.estimators_])
            pred_means = np.mean(tree_pred_matrix, axis=0)
            pred_stds = np.std(tree_pred_matrix, axis=0)
            y_pred = np.maximum(pred_means, 0)
            hist_std = float(np.std(y_train, ddof=1)) if len(y_train) > 1 else 5.0
            if not np.isfinite(hist_std):
                hist_std = 5.0
            ci_multiplier = 1.28
            open_flags = None
            if 'is_store_open' in df_features.columns:
                open_flags = df_features['is_store_open'].iloc[val_idx].values
            for idx, (dt, actual, predicted, pred_mean, pred_std) in enumerate(zip(dates.iloc[val_idx], y_val, y_pred, pred_means, pred_stds)):
                if open_flags is not None and float(open_flags[idx]) <= 0.0:
                    predicted_value = 0.0
                    lower = 0.0
                    upper = 0.0
                else:
                    predicted_value = float(max(0.0, predicted))
                    interval_radius = ci_multiplier * (float(pred_std) + hist_std * 0.3)
                    lower = float(max(0.0, pred_mean - interval_radius))
                    upper = float(max(predicted_value, pred_mean + interval_radius))
                rows.append({'date': dt, 'actual': float(actual), 'predicted': predicted_value, 'lower_bound': lower, 'upper_bound': upper})
        if not rows:
            return pd.DataFrame(columns=['date', 'actual', 'predicted', 'lower_bound', 'upper_bound'])
        return pd.DataFrame(rows).sort_values('date').reset_index(drop=True)

    def _calculate_horizon_metrics(self, *, store_id: str, meta: Dict[str, Any], raw_data: Optional[Dict[str, List[Dict[str, Any]]]]=None) -> Dict[str, Any]:
        """Hitung metric daily, weekly, monthly berbasis out-of-sample backtest."""
        if raw_data is None:
            return dict(meta.get('horizon_metrics') or {})
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)
        df_daily, _ = self._filter_daily_to_complete_period(
            df_daily,
            raw_data.get('operational_hours', []),
        )
        if df_daily.empty:
            return {}
        df_features = self.preprocessor.engineer_features(df_daily)
        feature_cols = self.preprocessor.get_feature_columns(df_features)
        oos_df = self._build_oos_daily_predictions(df_features, feature_cols)
        metrics: Dict[str, Any] = {'metrics_version': 'horizon-aware-oos-v2', 'metric_source': 'time_series_split_oos_daily_predictions', 'metric_note': 'weekly/monthly metrics are calculated by aggregating out-of-sample daily predictions into complete weekly/monthly periods.', 'daily_training_rows_before_features': int(len(df_daily)), 'daily_training_data_points': int(len(df_features)), 'oos_daily_prediction_points': int(len(oos_df))}
        if not oos_df.empty:
            metrics.update(self._metric_block('daily', oos_df['actual'].values, oos_df['predicted'].values, oos_df['lower_bound'].values if 'lower_bound' in oos_df.columns else None, oos_df['upper_bound'].values if 'upper_bound' in oos_df.columns else None))
            metrics.update(self._aggregate_oos_metric(oos_df, 'weekly'))
            metrics.update(self._aggregate_oos_metric(oos_df, 'monthly'))
        else:
            metrics.update(self._metric_block('daily', np.array([]), np.array([])))
            metrics.update(self._metric_block('weekly', np.array([]), np.array([])))
            metrics.update(self._metric_block('monthly', np.array([]), np.array([])))
        if not metrics.get('daily_metric_available') and meta.get('cv_mae') is not None:
            avg_actual = float(df_features['omzet'].mean()) if not df_features.empty else 0.0
            mae = float(meta.get('cv_mae', 0.0))
            rmse = float(meta.get('cv_rmse', 0.0))
            ratio = mae / avg_actual if avg_actual > 0 else None
            metrics.update({'daily_metric_available': True, 'daily_mae': self._round_metric(mae), 'daily_rmse': self._round_metric(rmse), 'daily_mae_percentage': self._round_metric(ratio * 100 if ratio is not None else None, 2), 'daily_error_ratio': self._round_metric(ratio, 4), 'daily_wape': self._round_metric(ratio, 4), 'daily_error_percentage': self._round_metric(ratio * 100 if ratio is not None else None, 2), 'daily_bias': None, 'daily_mean_error': None, 'daily_bias_percentage': None, 'daily_interval_coverage': None, 'daily_avg_interval_width': None, 'daily_relative_interval_width': None, 'daily_reliability': self._classify_reliability(ratio), 'metric_source': 'trainer_cv_fallback'})
        return metrics

    def _metadata_for_response(self, *, store_id: str, meta: Dict[str, Any], horizon_label: str, raw_data: Optional[Dict[str, List[Dict[str, Any]]]]=None) -> ModelMetadata:
        metrics = dict(meta.get('horizon_metrics') or {})
        if metrics.get('metrics_version') != 'horizon-aware-oos-v2':
            metrics = self._calculate_horizon_metrics(store_id=store_id, meta=meta, raw_data=raw_data)
            meta['horizon_metrics'] = metrics
            try:
                meta_path = trainer._meta_path(store_id, 'daily')
                with open(meta_path, 'w') as f:
                    json.dump(meta, f, indent=2)
            except Exception as exc:
                logger.warning(f'Gagal menyimpan horizon-aware metrics sales: {exc}')
        selected_mae = metrics.get(f'{horizon_label}_mae')
        selected_rmse = metrics.get(f'{horizon_label}_rmse')
        if selected_mae is None:
            selected_mae = metrics.get('daily_mae', meta.get('cv_mae'))
        if selected_rmse is None:
            selected_rmse = metrics.get('daily_rmse', meta.get('cv_rmse'))
        selected_metrics: Dict[str, Any] = {'metrics_version': metrics.get('metrics_version'), 'metric_source': metrics.get('metric_source'), 'training_rows_before_features': metrics.get('daily_training_rows_before_features'), 'training_data_points': metrics.get('daily_training_data_points'), 'oos_prediction_points': metrics.get('oos_daily_prediction_points'), f'{horizon_label}_metric_available': bool(metrics.get(f'{horizon_label}_metric_available', False)), f'{horizon_label}_mae': metrics.get(f'{horizon_label}_mae'), f'{horizon_label}_rmse': metrics.get(f'{horizon_label}_rmse'), f'{horizon_label}_mae_percentage': metrics.get(f'{horizon_label}_mae_percentage'), f'{horizon_label}_error_ratio': metrics.get(f'{horizon_label}_error_ratio'), f'{horizon_label}_wape': metrics.get(f'{horizon_label}_wape'), f'{horizon_label}_error_percentage': metrics.get(f'{horizon_label}_error_percentage'), f'{horizon_label}_bias': metrics.get(f'{horizon_label}_bias'), f'{horizon_label}_mean_error': metrics.get(f'{horizon_label}_mean_error'), f'{horizon_label}_bias_percentage': metrics.get(f'{horizon_label}_bias_percentage'), f'{horizon_label}_interval_coverage': metrics.get(f'{horizon_label}_interval_coverage'), f'{horizon_label}_avg_interval_width': metrics.get(f'{horizon_label}_avg_interval_width'), f'{horizon_label}_relative_interval_width': metrics.get(f'{horizon_label}_relative_interval_width'), f'{horizon_label}_reliability': metrics.get(f'{horizon_label}_reliability')}
        selected_metrics = {k: v for k, v in selected_metrics.items() if v is not None}
        return ModelMetadata(trained_at=datetime.fromisoformat(meta['trained_at']) if meta.get('trained_at') else None, training_data_points=int(meta.get('training_data_points', 0)), feature_importance=meta.get('top_features', meta.get('feature_importance', {})), cv_mae=self._round_metric(selected_mae), cv_rmse=self._round_metric(selected_rmse), horizon_method=self._horizon_method(horizon_label), metric_horizon=horizon_label, metrics=selected_metrics)
sales_forecast_service = SalesForecastService()