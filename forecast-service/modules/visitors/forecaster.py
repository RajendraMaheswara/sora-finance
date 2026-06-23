import os
import json
import httpx
import asyncio
import logging
import psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Tuple, Any, Optional
from pydantic import BaseModel, Field

from config import Config
from modules.visitors.trainer import trainer

# =========================================================================
# LOGGER SETUP
# =========================================================================

logger = logging.getLogger("visitors_forecaster")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
    logger.addHandler(ch)

# =========================================================================
# SCHEMAS
# =========================================================================

class DailyForecast(BaseModel):
    date: date
    predicted_visitors: int = Field(..., description="Prediksi jumlah pengunjung")
    predicted_transactions: int = Field(..., description="Prediksi jumlah transaksi")
    lower_bound: int = Field(..., description="Batas bawah prediksi (confidence interval)")
    upper_bound: int = Field(..., description="Batas atas prediksi (confidence interval)")
    day_of_week: str = Field(..., description="Nama hari (Senin, Selasa, dst)")
    is_weekend: bool

class WeeklyForecast(BaseModel):
    period_start: date
    period_end: date
    predicted_visitors: int
    predicted_transactions: int
    lower_bound: int
    upper_bound: int
    week_of_year: int
    year: int

class MonthlyForecast(BaseModel):
    period_start: date
    period_end: date
    predicted_visitors: int
    predicted_transactions: int
    lower_bound: int
    upper_bound: int
    month: int
    year: int

class ModelMetadata(BaseModel):
    trained_at: Optional[datetime]
    training_data_points: int
    feature_importance: dict
    cv_mae: float = Field(..., description="Mean Absolute Error dari cross-validation")
    cv_rmse: float = Field(..., description="Root Mean Squared Error dari cross-validation")

class ForecastResponse(BaseModel):
    store_id: str
    generated_at: datetime
    forecast_horizon_days: int
    forecasts: List[DailyForecast]
    model_metadata: ModelMetadata
    status: str = "success"
    message: str = ""
    model_config = {"protected_namespaces": ()}

class WeeklyForecastResponse(BaseModel):
    store_id: str
    generated_at: datetime
    forecast_horizon_weeks: int
    forecasts: List[WeeklyForecast]
    model_metadata: ModelMetadata
    status: str = "success"
    message: str = ""
    model_config = {"protected_namespaces": ()}

class MonthlyForecastResponse(BaseModel):
    store_id: str
    generated_at: datetime
    forecast_horizon_months: int
    forecasts: List[MonthlyForecast]
    model_metadata: ModelMetadata
    status: str = "success"
    message: str = ""
    model_config = {"protected_namespaces": ()}

class RetrainResponse(BaseModel):
    store_id: str
    status: str
    message: str
    training_data_points: int
    cv_mae: float
    cv_rmse: float
    trained_at: datetime
    feature_importance: dict


# =========================================================================
# CLIENTS (Golang & DB)
# =========================================================================

class GolangAPIClient:
    def __init__(self):
        self.base_url = Config.GOLANG_API_BASE_URL.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params, headers=Config.backend_headers())
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} on {url}: {e}")
                raise
            except httpx.RequestError as e:
                logger.warning(f"Request error attempt {attempt + 1}/3 on {url}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def is_reachable(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/stores")
                return response.status_code < 500
        except Exception:
            return False

    async def fetch_sales_daily_summaries(self, store_id: str) -> List[Dict]:
        logger.info(f"Fetching sales daily summaries for store {store_id}")
        try:
            data = await self._get("sales-daily-summaries", params={"store_id": store_id})
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get("data", data.get("items", []))
            return []
        except Exception as e:
            logger.error(f"Failed to fetch sales daily summaries: {e}")
            return []

    async def fetch_sales_monthly_summaries(self, store_id: str) -> List[Dict]:
        logger.info(f"Fetching sales monthly summaries for store {store_id}")
        try:
            data = await self._get("sales-monthly-summaries", params={"store_id": store_id})
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get("data", data.get("items", []))
            return []
        except Exception as e:
            logger.error(f"Failed to fetch sales monthly summaries: {e}")
            return []

    async def fetch_orders(self, store_id: str) -> List[Dict]:
        logger.info(f"Fetching orders for store {store_id}")
        try:
            data = await self._get("orders", params={"store_id": store_id})
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get("data", data.get("items", []))
            return []
        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            return []

    async def fetch_all_historical_data(self, store_id: str) -> Dict[str, List[Dict]]:
        logger.info(f"Fetching all historical data for store {store_id}")
        daily_task = self.fetch_sales_daily_summaries(store_id)
        monthly_task = self.fetch_sales_monthly_summaries(store_id)
        orders_task = self.fetch_orders(store_id)

        daily, monthly, orders = await asyncio.gather(
            daily_task, monthly_task, orders_task, return_exceptions=True
        )

        return {
            "sales_daily": daily if not isinstance(daily, Exception) else [],
            "sales_monthly": monthly if not isinstance(monthly, Exception) else [],
            "orders": orders if not isinstance(orders, Exception) else [],
        }

golang_client = GolangAPIClient()


class PostgresClient:
    def __init__(self) -> None:
        pass

    def _connect(self):
        required = {
            "DB_HOST": os.getenv("DB_HOST"),
            "DB_PORT": os.getenv("DB_PORT"),
            "DB_USER": os.getenv("DB_USER"),
            "DB_PASSWORD": os.getenv("DB_PASSWORD"),
            "DB_NAME": os.getenv("DB_NAME"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Konfigurasi database forecast-service belum lengkap: "
                f"{', '.join(missing)}. Isi forecast-service/.env lalu restart service."
            )

        return psycopg2.connect(
            host=required["DB_HOST"],
            port=required["DB_PORT"],
            user=required["DB_USER"],
            password=required["DB_PASSWORD"],
            dbname=required["DB_NAME"],
            sslmode=os.getenv("DB_SSLMODE", "disable"),
            connect_timeout=10,
        )

    def fetch_sales_daily_summaries(self, store_id: str) -> List[Dict[str, Any]]:
        sql = """
            SELECT date, total_transaction, total_omzet
            FROM t_sales_daily_summaries
            WHERE m_store_id = %s AND deleted_at IS NULL
            ORDER BY date ASC
        """
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f"DB error fetch_sales_daily_summaries: {exc}")
            return []

    def fetch_orders(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Ambil dataset harian visitors dari t_orders.

        Definisi visitors tahap ini dibuat konservatif dan tidak memakai bobot abstrak:
        - order valid non-online = 1 estimated physical visitor unit
        - order online = 0 pengunjung fisik outlet

        t_order_items sengaja tidak dipakai karena qty item tidak selalu merepresentasikan
        jumlah orang. t_sales_daily_summaries juga tidak menjadi target visitors lagi.
        """
        sql = """
            WITH valid_orders AS (
                SELECT
                    DATE(created_at AT TIME ZONE 'Asia/Jakarta') AS date,
                    id,
                    total_price,
                    m_table_id,
                    m_menu_online_order_type_id
                FROM t_orders
                WHERE m_store_id = %s
                  AND deleted_at IS NULL
                  AND cancelled_at IS NULL
                  AND COALESCE(m_order_status_id, 0) <> 3
                  AND (m_order_status_id = 2 OR m_order_payment_status_id = 200)
            )
            SELECT
                date,
                COUNT(*) FILTER (WHERE m_menu_online_order_type_id IS NULL)::integer AS visitors,
                COUNT(*)::integer AS valid_orders_count,
                COUNT(*) FILTER (WHERE m_menu_online_order_type_id IS NULL)::integer AS physical_orders_count,
                COUNT(*) FILTER (WHERE m_menu_online_order_type_id IS NOT NULL)::integer AS online_orders_count,
                COUNT(*) FILTER (
                    WHERE m_menu_online_order_type_id IS NULL
                      AND m_table_id IS NOT NULL
                )::integer AS dine_in_orders_count,
                COUNT(*) FILTER (
                    WHERE m_menu_online_order_type_id IS NULL
                      AND m_table_id IS NULL
                )::integer AS takeaway_orders_count,
                COALESCE(SUM(total_price), 0)::numeric(15,2) AS omzet
            FROM valid_orders
            GROUP BY date
            ORDER BY date ASC
        """
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f"DB error fetch_orders: {exc}")
            return []

    def fetch_store_operational_hours(self, store_id: str) -> List[Dict[str, Any]]:
        sql = """
            SELECT day_of_week, is_active, open_time, close_time
            FROM m_store_operational_hours
            WHERE m_store_id = %s
              AND deleted_at IS NULL
            ORDER BY day_of_week ASC
        """
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f"DB error fetch_store_operational_hours: {exc}")
            return []

    def fetch_all_historical_data(self, store_id: str) -> Dict[str, List[Dict[str, Any]]]:
        orders = self.fetch_orders(store_id)
        operational_hours = self.fetch_store_operational_hours(store_id)
        return {
            "sales_daily": [],
            "sales_monthly": [],
            "orders": orders,
            "operational_hours": operational_hours,
        }


    def save_visitors_forecast(
        self,
        *,
        store_id: str,
        horizon_label: str,
        horizon_days: int,
        prediction_rows: List[Dict[str, Any]],
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
        """
        Simpan hasil forecast visitors ke tabel public.forecast_runs dan
        public.forecast_results. Tabel forecast_predictions sudah tidak dipakai.
        """
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
                      AND forecast_type = 'visitors'
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
                        %s, 'visitors', %s, %s,
                        %s, 'random forest', %s, 'visitors-orders-operational-v2',
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
                            "visitors",
                        )
                        for row in result_rows
                    ],
                )

        return {
            "run_id": run_id,
            "saved_results": len(result_rows),
            "horizon_label": horizon_label,
            "horizon_days": horizon_days,
        }

db_client = PostgresClient()


# =========================================================================
# PREPROCESSING & FEATURE ENGINEERING
# =========================================================================

HARI_INDONESIA = {
    0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis",
    4: "Jumat", 5: "Sabtu", 6: "Minggu"
}

class VisitorPreprocessor:
    """
    Preprocessor visitors versi orders-based.

    Target visitors tidak lagi dari t_sales_daily_summaries.total_transaction.
    Target dibuat dari t_orders dengan definisi konservatif:
    visitors = jumlah order valid non-online per hari.

    t_order_items tidak dipakai karena qty item terlalu abstrak untuk jumlah orang.
    """

    UNKNOWN_NUMERIC_COLUMNS = {
        "valid_orders_count",
        "physical_orders_count",
        "online_orders_count",
        "dine_in_orders_count",
        "takeaway_orders_count",
        "online_ratio",
        "dine_in_ratio",
        "takeaway_ratio",
    }

    def build_daily_dataframe(self, raw_data: Dict[str, List[Dict]]) -> pd.DataFrame:
        df = self._build_from_orders(raw_data.get("orders", []))
        if df.empty:
            logger.error("Tidak ada data t_orders valid yang bisa digunakan untuk visitors")
            return pd.DataFrame()

        df = self._complete_daily_range(df)
        df = self._apply_operational_hours(df, raw_data.get("operational_hours", []))
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def build_weekly_dataframe(self, raw_data: Dict[str, List[Dict]]) -> pd.DataFrame:
        df_daily = self.build_daily_dataframe(raw_data)
        if df_daily.empty:
            return pd.DataFrame()

        df_daily = df_daily.copy()
        df_daily["date"] = pd.to_datetime(df_daily["date"])
        df_daily = df_daily.set_index("date").sort_index()

        weekly = df_daily.resample("W-SUN").sum(numeric_only=True)
        weekly = weekly.reset_index().rename(columns={"date": "period_end"})
        weekly["date"] = weekly["period_end"] - pd.Timedelta(days=6)
        return weekly[["date", "visitors", "omzet"]].copy()

    def build_monthly_dataframe(self, raw_data: Dict[str, List[Dict]]) -> pd.DataFrame:
        df_daily = self.build_daily_dataframe(raw_data)
        if df_daily.empty:
            return pd.DataFrame()

        df_daily = df_daily.copy()
        df_daily["date"] = pd.to_datetime(df_daily["date"])
        df_daily = df_daily.set_index("date").sort_index()

        monthly = df_daily.resample("MS").sum(numeric_only=True)
        monthly = monthly.reset_index()
        return monthly[["date", "visitors", "omzet"]].copy()

    def _build_from_sales_daily(self, records: List[Dict]) -> pd.DataFrame:
        """Legacy parser. Tidak dipakai sebagai target utama visitors."""
        if not records:
            return pd.DataFrame()
        try:
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["total_transaction"] = pd.to_numeric(
                df.get("total_transaction", df.get("totalTransaction", 0)), errors="coerce"
            ).fillna(0).astype(int)
            df["total_omzet"] = pd.to_numeric(
                df.get("total_omzet", df.get("totalOmzet", 0)), errors="coerce"
            ).fillna(0)
            return df[["date", "total_transaction", "total_omzet"]].rename(
                columns={"total_transaction": "visitors", "total_omzet": "omzet"}
            )
        except Exception as e:
            logger.error(f"Error parsing sales_daily: {e}")
            return pd.DataFrame()

    def _build_from_orders(self, records: List[Dict]) -> pd.DataFrame:
        if not records:
            return pd.DataFrame()
        try:
            df = pd.DataFrame(records)

            # Preferred path: DB query sudah mengembalikan agregasi harian.
            if "date" in df.columns and ("visitors" in df.columns or "estimated_visitors" in df.columns):
                if "estimated_visitors" in df.columns and "visitors" not in df.columns:
                    df = df.rename(columns={"estimated_visitors": "visitors"})

                df["date"] = pd.to_datetime(df["date"]).dt.date
                numeric_defaults = {
                    "visitors": 0,
                    "omzet": 0.0,
                    "valid_orders_count": 0,
                    "physical_orders_count": 0,
                    "online_orders_count": 0,
                    "dine_in_orders_count": 0,
                    "takeaway_orders_count": 0,
                }
                for col, default in numeric_defaults.items():
                    if col not in df.columns:
                        df[col] = default
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default)

                df["visitors"] = df["visitors"].clip(lower=0).round().astype(int)
                df["valid_orders_count"] = df["valid_orders_count"].clip(lower=0).round().astype(int)
                df["physical_orders_count"] = df["physical_orders_count"].clip(lower=0).round().astype(int)
                df["online_orders_count"] = df["online_orders_count"].clip(lower=0).round().astype(int)
                df["dine_in_orders_count"] = df["dine_in_orders_count"].clip(lower=0).round().astype(int)
                df["takeaway_orders_count"] = df["takeaway_orders_count"].clip(lower=0).round().astype(int)
                df["omzet"] = pd.to_numeric(df["omzet"], errors="coerce").fillna(0.0)
                df = self._add_order_ratios(df)
                return df[[
                    "date",
                    "visitors",
                    "omzet",
                    "valid_orders_count",
                    "physical_orders_count",
                    "online_orders_count",
                    "dine_in_orders_count",
                    "takeaway_orders_count",
                    "online_ratio",
                    "dine_in_ratio",
                    "takeaway_ratio",
                ]].copy()

            # Compatibility path jika suatu saat orders mentah dikirim dari backend.
            date_col = next((c for c in ["created_at", "createdAt", "date"] if c in df.columns), None)
            if not date_col:
                return pd.DataFrame()

            df["date"] = pd.to_datetime(df[date_col]).dt.date
            online_col = next((c for c in ["m_menu_online_order_type_id", "mMenuOnlineOrderTypeId"] if c in df.columns), None)
            table_col = next((c for c in ["m_table_id", "mTableId"] if c in df.columns), None)
            price_col = next((c for c in ["total_price", "totalPrice"] if c in df.columns), None)

            if online_col:
                df["is_online"] = df[online_col].notna()
            else:
                df["is_online"] = False

            if table_col:
                df["is_dine_in"] = (~df["is_online"]) & df[table_col].notna()
            else:
                df["is_dine_in"] = False

            df["is_takeaway"] = (~df["is_online"]) & (~df["is_dine_in"])
            df["estimated_visitors"] = (~df["is_online"]).astype(int)
            df["order_price"] = pd.to_numeric(df[price_col], errors="coerce").fillna(0.0) if price_col else 0.0

            daily = df.groupby("date").agg(
                visitors=("estimated_visitors", "sum"),
                omzet=("order_price", "sum"),
                valid_orders_count=("estimated_visitors", "count"),
                physical_orders_count=("estimated_visitors", "sum"),
                online_orders_count=("is_online", "sum"),
                dine_in_orders_count=("is_dine_in", "sum"),
                takeaway_orders_count=("is_takeaway", "sum"),
            ).reset_index()
            daily = self._add_order_ratios(daily)
            return daily
        except Exception as e:
            logger.error(f"Error parsing orders: {e}")
            return pd.DataFrame()

    def _add_order_ratios(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        denominator = df["valid_orders_count"].replace(0, np.nan)
        df["online_ratio"] = (df["online_orders_count"] / denominator).fillna(0.0)
        df["dine_in_ratio"] = (df["dine_in_orders_count"] / denominator).fillna(0.0)
        df["takeaway_ratio"] = (df["takeaway_orders_count"] / denominator).fillna(0.0)
        return df

    def _complete_daily_range(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        start_date = df["date"].min()
        end_date = df["date"].max()
        full_dates = pd.DataFrame({"date": pd.date_range(start_date, end_date, freq="D")})
        merged = full_dates.merge(df, on="date", how="left")

        numeric_cols = [c for c in merged.columns if c != "date"]
        for col in numeric_cols:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

        merged["date"] = merged["date"].dt.date
        return merged

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

        # Python dayofweek: Senin=0..Minggu=6.
        # DB project umumnya memakai 1..7. Support keduanya agar aman.
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

    def engineer_features(self, df: pd.DataFrame, lags: List[int] | None = None, windows: List[int] | None = None, expanding_min_periods: int | None = None) -> pd.DataFrame:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        lags = lags or [1, 2, 3, 7, 14, 21, 28]
        windows = windows or [7, 14, 28]
        max_lag = max(lags)
        expanding_min_periods = expanding_min_periods or max(7, min(windows))

        df["day_of_week"] = df["date"].dt.dayofweek
        df["day_of_month"] = df["date"].dt.day
        df["month"] = df["date"].dt.month
        df["quarter"] = df["date"].dt.quarter
        df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        df["is_month_start"] = df["date"].dt.is_month_start.astype(int)
        df["is_month_end"] = df["date"].dt.is_month_end.astype(int)

        # Default operational features jika data jam operasional tidak tersedia.
        if "is_store_open" not in df.columns:
            df["is_store_open"] = 1.0
        if "open_duration_hours" not in df.columns:
            df["open_duration_hours"] = 24.0
        if "is_24_hours" not in df.columns:
            df["is_24_hours"] = (df["open_duration_hours"] >= 23.99).astype(float)

        df["sin_dow"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["cos_dow"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
        df["sin_month"] = np.sin(2 * np.pi * df["month"] / 12)
        df["cos_month"] = np.cos(2 * np.pi * df["month"] / 12)

        for lag in lags:
            df[f"lag_{lag}"] = df["visitors"].shift(lag)

        for window in windows:
            df[f"rolling_mean_{window}"] = df["visitors"].shift(1).rolling(window=window, min_periods=1).mean()
            df[f"rolling_std_{window}"] = df["visitors"].shift(1).rolling(window=window, min_periods=1).std().fillna(0)
            df[f"rolling_max_{window}"] = df["visitors"].shift(1).rolling(window=window, min_periods=1).max()
            df[f"rolling_min_{window}"] = df["visitors"].shift(1).rolling(window=window, min_periods=1).min()

        df["expanding_mean"] = df["visitors"].shift(1).expanding(min_periods=expanding_min_periods).mean()

        if "omzet" in df.columns:
            df["omzet_per_visitor"] = (df["omzet"] / df["visitors"].replace(0, np.nan)).fillna(0)
            df["lag_omzet_7"] = df["omzet"].shift(7)
            df["rolling_omzet_7"] = df["omzet"].shift(1).rolling(7, min_periods=1).mean()

        # Lag/rolling untuk rasio channel aman karena hanya memakai histori masa lalu.
        for channel_col in ["online_ratio", "dine_in_ratio", "takeaway_ratio"]:
            if channel_col in df.columns:
                df[f"lag_{channel_col}_7"] = df[channel_col].shift(7)
                df[f"rolling_{channel_col}_7"] = df[channel_col].shift(1).rolling(7, min_periods=1).mean()

        df = df.dropna(subset=[f"lag_{max_lag}"]).reset_index(drop=True)
        return df

    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        # Kolom order count/ratio hari yang sama tidak boleh menjadi feature langsung
        # karena nilainya tidak diketahui saat forecast tanggal depan.
        exclude = {
            "date",
            "visitors",
            "omzet",
            "valid_orders_count",
            "physical_orders_count",
            "online_orders_count",
            "dine_in_orders_count",
            "takeaway_orders_count",
            "online_ratio",
            "dine_in_ratio",
            "takeaway_ratio",
        }
        return [c for c in df.columns if c not in exclude]

    def _build_future_row(
        self,
        target_date: pd.Timestamp,
        history: pd.DataFrame,
        lags: List[int] | None = None,
        windows: List[int] | None = None,
        operational_map: Optional[Dict[int, Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        row: Dict[str, Any] = {}
        lags = lags or [1, 2, 3, 7, 14, 21, 28]
        windows = windows or [7, 14, 28]

        row["day_of_week"] = target_date.dayofweek
        row["day_of_month"] = target_date.day
        row["month"] = target_date.month
        row["quarter"] = target_date.quarter
        row["week_of_year"] = target_date.isocalendar()[1]
        row["is_weekend"] = int(target_date.dayofweek in [5, 6])
        row["is_month_start"] = int(target_date.is_month_start)
        row["is_month_end"] = int(target_date.is_month_end)

        row.update(self._operational_features_for_date(target_date, operational_map))

        row["sin_dow"] = np.sin(2 * np.pi * row["day_of_week"] / 7)
        row["cos_dow"] = np.cos(2 * np.pi * row["day_of_week"] / 7)
        row["sin_month"] = np.sin(2 * np.pi * row["month"] / 12)
        row["cos_month"] = np.cos(2 * np.pi * row["month"] / 12)

        hist_visitors = history["visitors"].values
        for lag in lags:
            idx = len(hist_visitors) - lag
            row[f"lag_{lag}"] = float(hist_visitors[idx]) if idx >= 0 else 0.0

        for window in windows:
            recent = hist_visitors[-window:] if len(hist_visitors) >= window else hist_visitors
            row[f"rolling_mean_{window}"] = float(np.mean(recent)) if len(recent) > 0 else 0.0
            row[f"rolling_std_{window}"] = float(np.std(recent)) if len(recent) > 1 else 0.0
            row[f"rolling_max_{window}"] = float(np.max(recent)) if len(recent) > 0 else 0.0
            row[f"rolling_min_{window}"] = float(np.min(recent)) if len(recent) > 0 else 0.0

        row["expanding_mean"] = float(np.mean(hist_visitors)) if len(hist_visitors) > 0 else 0.0

        if "omzet" in history.columns:
            hist_omzet = pd.to_numeric(history["omzet"], errors="coerce").fillna(0).values
            row["lag_omzet_7"] = float(hist_omzet[-7]) if len(hist_omzet) >= 7 else 0.0
            recent_omzet = hist_omzet[-7:] if len(hist_omzet) >= 7 else hist_omzet
            row["rolling_omzet_7"] = float(np.mean(recent_omzet)) if len(recent_omzet) > 0 else 0.0
            row["omzet_per_visitor"] = 0.0
        else:
            row["omzet_per_visitor"] = 0.0
            row["lag_omzet_7"] = 0.0
            row["rolling_omzet_7"] = 0.0

        for channel_col in ["online_ratio", "dine_in_ratio", "takeaway_ratio"]:
            if channel_col in history.columns:
                hist_channel = pd.to_numeric(history[channel_col], errors="coerce").fillna(0).values
                row[f"lag_{channel_col}_7"] = float(hist_channel[-7]) if len(hist_channel) >= 7 else 0.0
                recent_channel = hist_channel[-7:] if len(hist_channel) >= 7 else hist_channel
                row[f"rolling_{channel_col}_7"] = float(np.mean(recent_channel)) if len(recent_channel) > 0 else 0.0
            else:
                row[f"lag_{channel_col}_7"] = 0.0
                row[f"rolling_{channel_col}_7"] = 0.0

        row["date"] = target_date
        return row


# =========================================================================
# FORECAST SERVICE
# =========================================================================

class ForecastService:
    def __init__(self):
        self.preprocessor = VisitorPreprocessor()
        self.period_configs = {
            "weekly": {
                "lags": [1, 2, 3, 4, 8, 12],
                "windows": [4, 8, 12],
                "expanding_min_periods": 4,
            },
            "monthly": {
                "lags": [1, 2, 3, 6, 12],
                "windows": [3, 6, 12],
                "expanding_min_periods": 3,
            },
        }
        self.feature_version = "visitors-orders-operational-v2"
        self.data_source = "t_orders_non_online_plus_operational_hours"

    def _tag_model_metadata(self, store_id: str, meta: Dict[str, Any], granularity: str = "daily") -> Dict[str, Any]:
        meta = dict(meta or {})
        meta["feature_version"] = self.feature_version
        meta["data_source"] = self.data_source
        meta["target_definition"] = "COUNT(valid t_orders where m_menu_online_order_type_id IS NULL)"
        try:
            meta_path = trainer._meta_path(store_id, granularity)
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
        except Exception as exc:
            logger.warning(f"Gagal menulis metadata model visitors: {exc}")
        return meta

    def _daily_model_needs_retrain(self, store_id: str) -> bool:
        if not trainer.model_exists(store_id):
            return True
        try:
            _, _, _, meta = trainer.load_model(store_id)
            return meta.get("feature_version") != self.feature_version
        except Exception as exc:
            logger.warning(f"Model visitors lama/tidak valid, akan retrain: {exc}")
            return True


    def _horizon_days(self, horizon_label: str, horizon_count: int) -> int:
        if horizon_label == "daily":
            return horizon_count
        if horizon_label == "weekly":
            return horizon_count * 7
        if horizon_label == "monthly":
            return horizon_count * 30
        raise ValueError("horizon_label harus daily, weekly, atau monthly")

    async def forecast_by_horizon(
        self,
        *,
        store_id: str,
        horizon_label: str,
        horizon_count: int,
        start_date: date | None = None,
    ):
        """Jalankan forecast visitors berdasarkan body standar route baru."""
        if horizon_count <= 0:
            raise ValueError("horizon_count harus lebih besar dari 0")

        if horizon_label == "daily":
            return await self.forecast(
                store_id=store_id,
                forecast_days=horizon_count,
                start_date=start_date or date.today(),
            )
        if horizon_label == "weekly":
            return await self.forecast_weekly(
                store_id=store_id,
                forecast_weeks=horizon_count,
                start_date=start_date,
            )
        if horizon_label == "monthly":
            return await self.forecast_monthly(
                store_id=store_id,
                forecast_months=horizon_count,
                start_date=start_date,
            )
        raise ValueError("horizon_label harus daily, weekly, atau monthly")

    def _date_to_iso(self, value: Any) -> str:
        if isinstance(value, pd.Timestamp):
            return value.date().isoformat()
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def _forecast_item_period_dates(self, item: Any, horizon_label: str) -> Tuple[date, date]:
        if horizon_label == "daily":
            return item.date, item.date
        return item.period_start, item.period_end

    def _forecast_item_to_row(
        self,
        *,
        item: Any,
        store_id: str,
        horizon_label: str,
        horizon_days: int,
        mae: float,
        rmse: float,
        mape: float | None,
        model_version: str,
        confidence_level: int,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if horizon_label == "daily":
            target_date = item.date
        else:
            target_date = item.period_start

        predicted_value = float(item.predicted_visitors)
        lower_bound = float(item.lower_bound) if item.lower_bound is not None else None
        upper_bound = float(item.upper_bound) if item.upper_bound is not None else None
        target_date_iso = self._date_to_iso(target_date)

        prediction_row = {
            "store_id": store_id,
            "module": "visitors",
            "horizon_label": horizon_label,
            "horizon_days": horizon_days,
            "prediction_date": target_date_iso,
            "predicted_value": predicted_value,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "mae": mae,
            "rmse": rmse,
            "mape": mape,
            "model_version": model_version,
        }
        result_row = {
            "target_date": target_date_iso,
            "predicted_value": predicted_value,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "confidence_level": confidence_level,
        }
        return prediction_row, result_row

    def _training_range(self, store_id: str) -> Tuple[date, date, int]:
        raw_data = db_client.fetch_all_historical_data(store_id)
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)
        if df_daily.empty:
            today = date.today()
            return today, today, 0

        dates = pd.to_datetime(df_daily["date"])
        return dates.min().date(), dates.max().date(), int(len(df_daily))

    def save_forecast_result(
        self,
        *,
        forecast_response: ForecastResponse | WeeklyForecastResponse | MonthlyForecastResponse,
        horizon_label: str,
        horizon_count: int,
    ) -> Dict[str, Any]:
        """Konversi response forecast visitors menjadi row database lalu simpan."""
        forecasts = forecast_response.forecasts
        if not forecasts:
            raise ValueError("Forecast kosong, tidak ada data untuk disimpan.")

        period_dates = [
            self._forecast_item_period_dates(item, horizon_label)
            for item in forecasts
        ]
        predict_start = min(start for start, _ in period_dates)
        predict_end = max(end for _, end in period_dates)
        horizon_days = (predict_end - predict_start).days + 1

        metadata = forecast_response.model_metadata
        mae = float(metadata.cv_mae)
        rmse = float(metadata.cv_rmse)
        mape = None
        model_version = "visitors-rf-v2"

        avg_prediction = max(
            1.0,
            float(np.mean([max(0, item.predicted_visitors) for item in forecasts])),
        )
        error_ratio = min(100.0, (mae / avg_prediction) * 100.0)
        confidence_level = int(max(0, min(100, round(100.0 - error_ratio))))

        prediction_rows: List[Dict[str, Any]] = []
        result_rows: List[Dict[str, Any]] = []
        for item in forecasts:
            prediction_row, result_row = self._forecast_item_to_row(
                item=item,
                store_id=forecast_response.store_id,
                horizon_label=horizon_label,
                horizon_days=horizon_days,
                mae=mae,
                rmse=rmse,
                mape=mape,
                model_version=model_version,
                confidence_level=confidence_level,
            )
            prediction_rows.append(prediction_row)
            result_rows.append(result_row)

        train_start, train_end, raw_train_rows = self._training_range(forecast_response.store_id)

        metrics = {
            "mae": mae,
            "rmse": rmse,
            "mape": mape,
            "confidence_level": confidence_level,
        }
        summary = {
            "module": "visitors",
            "horizon_label": horizon_label,
            "horizon_count": horizon_count,
            "horizon_days": horizon_days,
            "prediction_count": len(prediction_rows),
            "total_predicted_visitors": int(sum(row["predicted_value"] for row in prediction_rows)),
            "average_predicted_visitors": round(avg_prediction, 2),
            "generated_at": forecast_response.generated_at.isoformat(),
        }
        data_quality = {
            "training_rows": raw_train_rows,
            "model_training_data_points": metadata.training_data_points,
            "date_range": {
                "start": train_start.isoformat(),
                "end": train_end.isoformat(),
            },
        }

        save_result = db_client.save_visitors_forecast(
            store_id=forecast_response.store_id,
            horizon_label=horizon_label,
            horizon_days=horizon_days,
            prediction_rows=prediction_rows,
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
        save_result["metrics"] = metrics
        save_result["summary"] = summary
        return save_result

    async def retrain(self, store_id: str, force: bool = False) -> RetrainResponse:
        logger.info(f"[RETRAIN] store={store_id}, force={force}")
        raw_data = db_client.fetch_all_historical_data(store_id)
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)
        
        if df_daily.empty:
            raise ValueError(f"Tidak ada data historis untuk store {store_id}.")

        if len(df_daily) < 30:
            raise ValueError(f"Data historis terlalu sedikit: {len(df_daily)} hari. Minimal 30 hari data.")

        df_features = self.preprocessor.engineer_features(df_daily)
        feature_cols = self.preprocessor.get_feature_columns(df_features)

        meta = trainer.train(df_features, feature_cols, store_id)
        meta = self._tag_model_metadata(store_id, meta)

        return RetrainResponse(
            store_id=store_id,
            status="success",
            message=f"Model berhasil dilatih dengan {meta['training_data_points']} data points",
            training_data_points=meta["training_data_points"],
            cv_mae=meta["cv_mae"],
            cv_rmse=meta["cv_rmse"],
            trained_at=datetime.fromisoformat(meta["trained_at"]),
            feature_importance=meta["top_features"],
        )

    async def forecast(self, store_id: str, forecast_days: int, start_date: date) -> ForecastResponse:
        logger.info(f"[FORECAST] store={store_id}, days={forecast_days}, start={start_date}")

        if self._daily_model_needs_retrain(store_id):
            logger.info(
                f"Model visitors belum ada atau masih memakai feature lama; "
                f"auto-training ulang untuk store {store_id}..."
            )
            await self.retrain(store_id)

        model, scaler, feature_cols, meta = trainer.load_model(store_id)
        raw_data = db_client.fetch_all_historical_data(store_id)
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)

        if df_daily.empty:
            raise ValueError(f"Tidak ada data historis untuk store {store_id}")

        hist_std = float(df_daily["visitors"].std()) if len(df_daily) > 1 else 5.0
        ci_multiplier = 1.28

        forecasts = []
        history_cols = [
            col for col in [
                "date",
                "visitors",
                "omzet",
                "online_ratio",
                "dine_in_ratio",
                "takeaway_ratio",
            ]
            if col in df_daily.columns
        ]
        running_history = df_daily[history_cols].copy()
        running_history["date"] = pd.to_datetime(running_history["date"])
        operational_map = self.preprocessor._parse_operational_hours(raw_data.get("operational_hours", []))

        for day_offset in range(forecast_days):
            target_date = pd.Timestamp(start_date) + timedelta(days=day_offset)
            row = self.preprocessor._build_future_row(
                target_date,
                running_history,
                operational_map=operational_map,
            )
            X_row = np.array([[row.get(col, 0.0) for col in feature_cols]])
            X_scaled = scaler.transform(X_row)

            tree_preds = np.array([tree.predict(X_scaled)[0] for tree in model.estimators_])
            pred_mean = float(np.mean(tree_preds))
            pred_std = float(np.std(tree_preds))

            if float(row.get("is_store_open", 1.0)) <= 0.0:
                predicted_visitors = 0
                lower = 0
                upper = 0
            else:
                predicted_visitors = max(0, round(pred_mean))
                lower = max(0, round(pred_mean - ci_multiplier * (pred_std + hist_std * 0.3)))
                upper = max(predicted_visitors, round(pred_mean + ci_multiplier * (pred_std + hist_std * 0.3)))

            day_name = HARI_INDONESIA.get(target_date.dayofweek, "")
            is_weekend = target_date.dayofweek in [5, 6]

            forecasts.append(DailyForecast(
                date=target_date.date(),
                predicted_visitors=predicted_visitors,
                predicted_transactions=predicted_visitors,
                lower_bound=lower,
                upper_bound=upper,
                day_of_week=day_name,
                is_weekend=is_weekend,
            ))

            new_history = {
                "date": target_date,
                "visitors": float(predicted_visitors),
            }
            if "omzet" in running_history.columns:
                new_history["omzet"] = float(row.get("rolling_omzet_7", 0.0))
            for channel_col in ["online_ratio", "dine_in_ratio", "takeaway_ratio"]:
                if channel_col in running_history.columns:
                    new_history[channel_col] = float(row.get(f"rolling_{channel_col}_7", 0.0))
            running_history = pd.concat([running_history, pd.DataFrame([new_history])], ignore_index=True)

        return ForecastResponse(
            store_id=store_id,
            generated_at=datetime.utcnow(),
            forecast_horizon_days=forecast_days,
            forecasts=forecasts,
            model_metadata=ModelMetadata(
                trained_at=datetime.fromisoformat(meta["trained_at"]),
                training_data_points=meta["training_data_points"],
                feature_importance=meta.get("top_features", {}),
                cv_mae=meta["cv_mae"],
                cv_rmse=meta["cv_rmse"],
            ),
            status="success",
            message=f"Berhasil memprediksi {forecast_days} hari ke depan",
        )

    def _get_period_config(self, granularity: str) -> Dict[str, Any]:
        if granularity not in self.period_configs:
            raise ValueError(f"Granularity tidak dikenal: {granularity}")
        return self.period_configs[granularity]

    def _align_start_date(self, start: date, granularity: str) -> pd.Timestamp:
        ts = pd.Timestamp(start)
        if granularity == "weekly":
            return ts - pd.Timedelta(days=ts.dayofweek)
        if granularity == "monthly":
            return ts.replace(day=1)
        return ts

    def _next_start_date(self, last_date: pd.Timestamp, granularity: str) -> pd.Timestamp:
        if granularity == "weekly":
            days_to_add = 7 - last_date.dayofweek
            return (last_date + pd.Timedelta(days=days_to_add)).normalize()
        if granularity == "monthly":
            return (last_date + pd.offsets.MonthBegin(1)).normalize()
        return last_date

    def _add_periods(self, start: pd.Timestamp, offset: int, granularity: str) -> pd.Timestamp:
        if granularity == "weekly":
            return start + pd.Timedelta(weeks=offset)
        if granularity == "monthly":
            return start + pd.DateOffset(months=offset)
        return start

    async def _retrain_periodic(self, store_id: str, granularity: str) -> Dict[str, Any]:
        raw_data = db_client.fetch_all_historical_data(store_id)
        if granularity == "weekly":
            df_period = self.preprocessor.build_weekly_dataframe(raw_data)
        else:
            df_period = self.preprocessor.build_monthly_dataframe(raw_data)

        if df_period.empty:
            raise ValueError(f"Tidak ada data historis untuk store {store_id}.")

        config = self._get_period_config(granularity)
        min_points = max(config["lags"]) + 1
        if len(df_period) < min_points:
            raise ValueError(f"Data historis terlalu sedikit: {len(df_period)} {granularity}. Minimal {min_points} periode.")

        df_features = self.preprocessor.engineer_features(
            df_period,
            lags=config["lags"],
            windows=config["windows"],
            expanding_min_periods=config["expanding_min_periods"],
        )
        feature_cols = self.preprocessor.get_feature_columns(df_features)

        meta = trainer.train(df_features, feature_cols, store_id, granularity=granularity)
        return meta

    async def _forecast_periodic(self, store_id: str, forecast_periods: int, start_date: date | None, granularity: str):
        if not trainer.model_exists(store_id, granularity=granularity):
            logger.info(f"Model {granularity} belum ada untuk store {store_id}, auto-training...")
            await self._retrain_periodic(store_id, granularity)

        model, scaler, feature_cols, meta = trainer.load_model(store_id, granularity=granularity)
        raw_data = db_client.fetch_all_historical_data(store_id)
        
        if granularity == "weekly":
            df_period = self.preprocessor.build_weekly_dataframe(raw_data)
        else:
            df_period = self.preprocessor.build_monthly_dataframe(raw_data)

        if df_period.empty:
            raise ValueError(f"Tidak ada data historis untuk store {store_id}")

        hist_std = float(df_period["visitors"].std()) if len(df_period) > 1 else 5.0
        ci_multiplier = 1.28

        running_history = df_period[["date", "visitors"]].copy()
        running_history["date"] = pd.to_datetime(running_history["date"])

        if start_date:
            start = self._align_start_date(start_date, granularity)
        else:
            start = self._next_start_date(running_history["date"].max(), granularity)

        config = self._get_period_config(granularity)
        forecasts = []

        for offset in range(forecast_periods):
            target_date = self._add_periods(start, offset, granularity)
            row = self.preprocessor._build_future_row(target_date, running_history, lags=config["lags"], windows=config["windows"])
            X_row = np.array([[row.get(col, 0.0) for col in feature_cols]])
            X_scaled = scaler.transform(X_row)

            tree_preds = np.array([tree.predict(X_scaled)[0] for tree in model.estimators_])
            pred_mean = float(np.mean(tree_preds))
            pred_std = float(np.std(tree_preds))

            predicted_visitors = max(0, round(pred_mean))
            lower = max(0, round(pred_mean - ci_multiplier * (pred_std + hist_std * 0.3)))
            upper = max(predicted_visitors, round(pred_mean + ci_multiplier * (pred_std + hist_std * 0.3)))

            if granularity == "weekly":
                forecasts.append(WeeklyForecast(
                    period_start=target_date.date(),
                    period_end=(target_date + timedelta(days=6)).date(),
                    predicted_visitors=predicted_visitors,
                    predicted_transactions=predicted_visitors,
                    lower_bound=lower,
                    upper_bound=upper,
                    week_of_year=int(target_date.isocalendar()[1]),
                    year=int(target_date.year),
                ))
            else:
                forecasts.append(MonthlyForecast(
                    period_start=target_date.date(),
                    period_end=(target_date + pd.offsets.MonthEnd(0)).date(),
                    predicted_visitors=predicted_visitors,
                    predicted_transactions=predicted_visitors,
                    lower_bound=lower,
                    upper_bound=upper,
                    month=int(target_date.month),
                    year=int(target_date.year),
                ))

            new_row = pd.DataFrame([{"date": target_date, "visitors": float(predicted_visitors)}])
            running_history = pd.concat([running_history, new_row], ignore_index=True)

        return forecasts, meta

    def _build_weekly_from_daily_response(
        self,
        *,
        daily_response: ForecastResponse,
        forecast_weeks: int,
    ) -> List[WeeklyForecast]:
        """Agregasi forecast harian menjadi periode 7 hari berurutan."""
        daily_items = sorted(daily_response.forecasts, key=lambda item: item.date)
        weekly_forecasts: List[WeeklyForecast] = []

        for week_index in range(forecast_weeks):
            chunk = daily_items[week_index * 7:(week_index + 1) * 7]
            if not chunk:
                break

            period_start = chunk[0].date
            period_end = chunk[-1].date
            predicted_visitors = int(sum(item.predicted_visitors for item in chunk))
            predicted_transactions = int(sum(item.predicted_transactions for item in chunk))
            lower_bound = int(sum(item.lower_bound for item in chunk))
            upper_bound = int(sum(item.upper_bound for item in chunk))

            weekly_forecasts.append(WeeklyForecast(
                period_start=period_start,
                period_end=period_end,
                predicted_visitors=predicted_visitors,
                predicted_transactions=predicted_transactions,
                lower_bound=lower_bound,
                upper_bound=max(predicted_visitors, upper_bound),
                week_of_year=int(pd.Timestamp(period_start).isocalendar()[1]),
                year=int(period_start.year),
            ))

        return weekly_forecasts

    def _monthly_periods(
        self,
        *,
        forecast_months: int,
        start_date: date | None,
    ) -> List[Tuple[date, date]]:
        """
        Bentuk periode bulanan berbasis kalender asli.

        - Jika start_date dikirim, bulan pertama mengikuti bulan start_date.
        - Jika start_date kosong, forecast dimulai dari bulan penuh berikutnya,
          agar monthly tidak menjadi bulan parsial dari hari ini.
        """
        if forecast_months <= 0:
            return []

        if start_date:
            first_month = pd.Timestamp(start_date).replace(day=1).normalize()
        else:
            first_month = (pd.Timestamp(date.today()) + pd.offsets.MonthBegin(1)).normalize()

        periods: List[Tuple[date, date]] = []
        for offset in range(forecast_months):
            period_start = (first_month + pd.DateOffset(months=offset)).normalize()
            period_end = (period_start + pd.offsets.MonthEnd(0)).normalize()
            periods.append((period_start.date(), period_end.date()))

        return periods

    def _build_monthly_from_daily_response(
        self,
        *,
        daily_response: ForecastResponse,
        periods: List[Tuple[date, date]],
    ) -> List[MonthlyForecast]:
        """Agregasi forecast harian menjadi bulan kalender."""
        daily_items = sorted(daily_response.forecasts, key=lambda item: item.date)
        monthly_forecasts: List[MonthlyForecast] = []

        for period_start, period_end in periods:
            chunk = [
                item for item in daily_items
                if period_start <= item.date <= period_end
            ]
            if not chunk:
                continue

            predicted_visitors = int(sum(item.predicted_visitors for item in chunk))
            predicted_transactions = int(sum(item.predicted_transactions for item in chunk))
            lower_bound = int(sum(item.lower_bound for item in chunk))
            upper_bound = int(sum(item.upper_bound for item in chunk))

            monthly_forecasts.append(MonthlyForecast(
                period_start=period_start,
                period_end=period_end,
                predicted_visitors=predicted_visitors,
                predicted_transactions=predicted_transactions,
                lower_bound=lower_bound,
                upper_bound=max(predicted_visitors, upper_bound),
                month=int(period_start.month),
                year=int(period_start.year),
            ))

        return monthly_forecasts

    async def forecast_weekly(self, store_id: str, forecast_weeks: int, start_date: date | None) -> WeeklyForecastResponse:
        """
        Weekly visitors forecast memakai best practice untuk data pendek:
        jalankan model daily, lalu jumlahkan setiap 7 hari.
        """
        if forecast_weeks <= 0:
            raise ValueError("forecast_weeks harus lebih besar dari 0")

        daily_start = start_date or date.today()
        daily_response = await self.forecast(
            store_id=store_id,
            forecast_days=forecast_weeks * 7,
            start_date=daily_start,
        )
        forecasts = self._build_weekly_from_daily_response(
            daily_response=daily_response,
            forecast_weeks=forecast_weeks,
        )

        return WeeklyForecastResponse(
            store_id=store_id,
            generated_at=datetime.utcnow(),
            forecast_horizon_weeks=forecast_weeks,
            forecasts=forecasts,
            model_metadata=daily_response.model_metadata,
            status="success",
            message=(
                f"Berhasil memprediksi {forecast_weeks} minggu ke depan "
                "dari agregasi daily forecast"
            ),
        )

    async def forecast_monthly(self, store_id: str, forecast_months: int, start_date: date | None) -> MonthlyForecastResponse:
        """
        Monthly visitors forecast memakai best practice untuk data pendek:
        jalankan model daily sampai akhir bulan target, lalu jumlahkan per bulan kalender.
        """
        if forecast_months <= 0:
            raise ValueError("forecast_months harus lebih besar dari 0")

        periods = self._monthly_periods(
            forecast_months=forecast_months,
            start_date=start_date,
        )
        if not periods:
            raise ValueError("Periode monthly forecast kosong")

        daily_start = periods[0][0]
        daily_end = periods[-1][1]
        forecast_days = (daily_end - daily_start).days + 1

        daily_response = await self.forecast(
            store_id=store_id,
            forecast_days=forecast_days,
            start_date=daily_start,
        )
        forecasts = self._build_monthly_from_daily_response(
            daily_response=daily_response,
            periods=periods,
        )

        return MonthlyForecastResponse(
            store_id=store_id,
            generated_at=datetime.utcnow(),
            forecast_horizon_months=forecast_months,
            forecasts=forecasts,
            model_metadata=daily_response.model_metadata,
            status="success",
            message=(
                f"Berhasil memprediksi {forecast_months} bulan ke depan "
                "dari agregasi daily forecast"
            ),
        )

forecast_service = ForecastService()
