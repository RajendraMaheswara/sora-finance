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
from contextlib import contextmanager
from typing import Dict, List, Tuple, Any, Optional
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler

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

    # Backward-compatible legacy fields. Nilainya mengikuti horizon aktif.
    cv_mae: Optional[float] = Field(None, description="Legacy MAE; sama dengan MAE horizon aktif")
    cv_rmse: Optional[float] = Field(None, description="Legacy RMSE; sama dengan RMSE horizon aktif")

    # New horizon-aware metadata. Field metric horizon aktif ditambahkan dinamis,
    # misalnya monthly_mae hanya muncul pada response monthly.
    horizon_method: Optional[str] = None
    metric_horizon: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow", "protected_namespaces": ()}

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
        # Orders diambil paginated. Order-items di backend saat ini bisa lambat,
        # jadi read timeout dibuat lebih panjang agar request tidak putus saat
        # backend masih memproses.
        self.timeout = httpx.Timeout(45.0, connect=10.0, read=45.0, write=10.0, pool=10.0)
        self.long_timeout = httpx.Timeout(120.0, connect=10.0, read=120.0, write=10.0, pool=10.0)
        self.page_limit = 200
        self.max_pages = 50

    def _extract_items(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("data", "items", "results"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

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
                    response = await client.get(url, params=params, headers=Config.backend_headers())
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} on {url}: {e}")
                raise
            except httpx.RequestError as e:
                logger.warning(f"Request error attempt {attempt + 1}/{attempts} on {url}: {e}")
                if attempt < attempts - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def is_reachable(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/stores", headers=Config.backend_headers())
                return response.status_code < 500
        except Exception:
            return False

    def _same_store(self, item: Dict[str, Any], store_id: str) -> bool:
        value = item.get("m_store_id") or item.get("store_id") or item.get("storeId") or item.get("mStoreId")
        return str(value) == str(store_id)

    async def fetch_orders(self, store_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Fetching orders for store {store_id} via backend API (paginated)")
        all_items: List[Dict[str, Any]] = []

        for page in range(1, self.max_pages + 1):
            params = {"store_id": store_id, "page": page, "limit": self.page_limit}
            data = await self._get("orders", params=params, timeout=self.long_timeout, attempts=2)
            items = self._extract_items(data)
            if not items:
                break

            filtered = [item for item in items if self._same_store(item, store_id)]
            # Internal route kadang sudah scoped oleh backend. Jika field store_id tidak
            # terbaca di response lama, jangan drop semua data; pakai items apa adanya.
            batch = filtered or items
            all_items.extend(batch)

            logger.info(
                "Fetched orders page=%s limit=%s rows=%s total=%s",
                page, self.page_limit, len(batch), len(all_items),
            )
            if len(items) < self.page_limit:
                break

        # Deduplicate jika backend mengembalikan row yang sama lintas page.
        deduped: Dict[str, Dict[str, Any]] = {}
        for item in all_items:
            order_id = self._order_id(item)
            if order_id:
                deduped[order_id] = item
        result = list(deduped.values()) if deduped else all_items
        logger.info("Fetched total orders for visitors: %s", len(result))
        return result

    async def fetch_order_items(self, store_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Fetching order items for store {store_id} via backend API")
        try:
            # Backend order-items saat ini belum punya pagination/filter khusus dan bisa
            # lambat. Pakai timeout lebih panjang dan 1 attempt supaya tidak membuat
            # tiga request berat bertumpuk. Jika gagal, visitors tetap jalan dengan
            # fallback qty=0 per order.
            data = await self._get(
                "order-items",
                params={"store_id": store_id},
                timeout=self.long_timeout,
                attempts=1,
            )
            items = self._extract_items(data)
            filtered = [item for item in items if self._same_store(item, store_id)]
            result = filtered or items
            logger.info("Fetched order items for visitors: %s", len(result))
            return result
        except Exception as exc:
            # Jika endpoint order-items belum siap/lambat, visitors tetap bisa jalan dengan
            # fallback 1 non-online order = 1 visitor.
            logger.warning(f"Failed to fetch order items via backend API, fallback qty=0: {exc}")
            return []

    async def fetch_visitors_daily_history(self, store_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Fetching visitors daily history for store {store_id} via backend API")
        try:
            data = await self._get(
                "visitors-daily-history",
                params={"store_id": store_id},
                timeout=self.long_timeout,
                attempts=1,
            )
            items = self._extract_items(data)
            logger.info("Fetched visitors daily history rows: %s", len(items))
            return items
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Backend visitors-daily-history endpoint belum tersedia; fallback ke paginated raw orders")
                return []
            raise
        except Exception as exc:
            logger.warning(f"Failed to fetch visitors daily history via backend API; fallback ke paginated raw orders: {exc}")
            return []

    async def fetch_store_operational_hours(self, store_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Fetching operational hours for store {store_id} via backend API")
        try:
            data = await self._get("store-operational-hours", params={"store_id": store_id})
            items = self._extract_items(data)
            return [item for item in items if self._same_store(item, store_id)]
        except Exception as exc:
            # Internal forecast routes di backend lama belum menyediakan
            # /store-operational-hours. Jangan fallback ke DB direct karena itu yang
            # memicu EMAXCONNSESSION. Preprocessor otomatis memakai default toko buka 24 jam.
            logger.warning(f"Failed to fetch operational hours via backend API, fallback open 24h: {exc}")
            return []

    def _is_blank(self, value: Any) -> bool:
        return value is None or value == "" or str(value).lower() in {"null", "none"}

    def _float_value(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _int_value(self, value: Any, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except Exception:
            return default

    def _date_from_order(self, order: Dict[str, Any]) -> Optional[date]:
        raw = order.get("created_at") or order.get("createdAt") or order.get("date")
        if not raw:
            return None
        try:
            return pd.to_datetime(raw).date()
        except Exception:
            return None

    def _is_valid_order(self, order: Dict[str, Any]) -> bool:
        if not self._is_blank(order.get("deleted_at") or order.get("deletedAt")):
            return False
        if not self._is_blank(order.get("cancelled_at") or order.get("cancelledAt")):
            return False
        status = self._int_value(order.get("m_order_status_id") or order.get("mOrderStatusId"), 0)
        payment_status = self._int_value(order.get("m_order_payment_status_id") or order.get("mOrderPaymentStatusId"), 0)
        if status == 3:
            return False
        return status == 2 or payment_status == 200

    def _order_id(self, order: Dict[str, Any]) -> str:
        return str(order.get("id") or order.get("order_id") or order.get("orderId") or "")

    def _order_item_order_id(self, item: Dict[str, Any]) -> str:
        return str(item.get("t_order_id") or item.get("order_id") or item.get("orderId") or item.get("tOrderId") or "")

    def _aggregate_order_item_qty(self, order_items: List[Dict[str, Any]]) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for item in order_items:
            if not self._is_blank(item.get("deleted_at") or item.get("deletedAt")):
                continue
            order_id = self._order_item_order_id(item)
            if not order_id:
                continue
            qty = max(0.0, self._float_value(item.get("qty"), 0.0))
            totals[order_id] = totals.get(order_id, 0.0) + qty
        return totals

    def _estimate_visitors(self, is_online: bool, total_item_qty: float) -> int:
        if is_online:
            return 0
        if total_item_qty <= 0:
            return 1
        if total_item_qty <= 3:
            return 1
        if total_item_qty <= 5:
            return 2
        if total_item_qty <= 8:
            return 3
        return 4

    def _build_daily_orders_from_backend(
        self,
        *,
        store_id: str,
        orders: List[Dict[str, Any]],
        order_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        item_qty_by_order = self._aggregate_order_item_qty(order_items)
        grouped: Dict[date, Dict[str, Any]] = {}

        for order in orders:
            if not self._same_store(order, store_id):
                continue
            if not self._is_valid_order(order):
                continue
            order_date = self._date_from_order(order)
            if order_date is None:
                continue

            online_type = order.get("m_menu_online_order_type_id") or order.get("mMenuOnlineOrderTypeId")
            table_id = order.get("m_table_id") or order.get("mTableId")
            is_online = not self._is_blank(online_type)
            is_dine_in = (not is_online) and (not self._is_blank(table_id))
            is_takeaway = (not is_online) and (not is_dine_in)
            order_id = self._order_id(order)
            total_item_qty = max(0.0, item_qty_by_order.get(order_id, 0.0))
            estimated_visitors = self._estimate_visitors(is_online, total_item_qty)

            row = grouped.setdefault(order_date, {
                "date": order_date,
                "visitors": 0,
                "valid_orders_count": 0,
                "physical_orders_count": 0,
                "online_orders_count": 0,
                "dine_in_orders_count": 0,
                "takeaway_orders_count": 0,
                "physical_item_qty": 0.0,
                "avg_physical_item_qty": 0.0,
            })
            row["visitors"] += estimated_visitors
            row["valid_orders_count"] += 1
            if is_online:
                row["online_orders_count"] += 1
            else:
                row["physical_orders_count"] += 1
                row["physical_item_qty"] += total_item_qty
                if is_dine_in:
                    row["dine_in_orders_count"] += 1
                if is_takeaway:
                    row["takeaway_orders_count"] += 1

        rows = []
        for _, row in sorted(grouped.items(), key=lambda item: item[0]):
            physical_orders = max(int(row.get("physical_orders_count", 0)), 0)
            row["avg_physical_item_qty"] = (
                float(row.get("physical_item_qty", 0.0)) / physical_orders
                if physical_orders > 0 else 0.0
            )
            rows.append(row)
        return rows

    async def fetch_all_historical_data(self, store_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Visitors sengaja memakai backend/internal API, sama seperti sales.
        Ini menghindari forecast-service membuka koneksi PostgreSQL langsung untuk
        retrain/preview, sehingga tidak menambah session baru di Supabase pooler.
        """
        logger.info(f"Fetching visitors historical data for store {store_id} via backend API")
        operational_hours = await self.fetch_store_operational_hours(store_id)

        # Fast path untuk forecast: backend mengembalikan data harian yang sudah
        # diagregasi dari t_orders + t_order_items. Ini menghindari 50+ request
        # pagination raw orders dan endpoint order-items yang berat.
        daily_orders = await self.fetch_visitors_daily_history(store_id)
        if daily_orders:
            dates = [row.get("date") for row in daily_orders if row.get("date") is not None]
            logger.info(
                "Fetched visitors daily history: daily_rows=%s range=%s..%s",
                len(daily_orders), min(dates) if dates else None, max(dates) if dates else None,
            )
            return {
                "orders": daily_orders,
                "operational_hours": operational_hours,
            }

        # Fallback untuk backend lama: tetap bisa jalan dengan pagination raw orders,
        # tetapi ini lebih lambat dan hanya dipakai kalau endpoint agregasi belum ada.
        orders = await self.fetch_orders(store_id)
        order_items = await self.fetch_order_items(store_id)

        daily_orders = self._build_daily_orders_from_backend(
            store_id=store_id,
            orders=orders,
            order_items=order_items,
        )
        if daily_orders:
            dates = [row.get("date") for row in daily_orders if row.get("date") is not None]
            logger.info(
                "Built visitors daily history fallback: raw_orders=%s order_items=%s daily_rows=%s range=%s..%s",
                len(orders), len(order_items), len(daily_orders),
                min(dates) if dates else None, max(dates) if dates else None,
            )
        else:
            logger.warning(
                "Visitors daily history kosong setelah parsing backend API: raw_orders=%s order_items=%s",
                len(orders), len(order_items),
            )
        return {
            "orders": daily_orders,
            "operational_hours": operational_hours,
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

    @contextmanager
    def _connection(self):
        conn = None
        try:
            conn = self._connect()
            yield conn
            conn.commit()
        except Exception:
            if conn is not None:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()

    def fetch_orders(self, store_id: str, conn=None) -> List[Dict[str, Any]]:
        """
        Ambil dataset harian visitors dari t_orders + t_order_items.

        Definisi visitors memakai mode items_capped:
        - order online = 0 pengunjung fisik outlet
        - order fisik dengan 0-3 item = 1 visitor
        - order fisik dengan 4-5 item = 2 visitors
        - order fisik dengan 6-8 item = 3 visitors
        - order fisik dengan >8 item = 4 visitors

        Rule ini tidak bergantung pada kategori menu sehingga tetap cocok untuk cafe
        yang hanya menjual kopi/minuman, warmindo, resto, atau F&B lain tanpa perlu
        menambah tabel/kolom konfigurasi baru.
        """
        sql = """
            WITH order_item_totals AS (
                SELECT
                    t_order_id,
                    COALESCE(SUM(GREATEST(COALESCE(qty, 0), 0)), 0)::numeric(15,2) AS total_item_qty
                FROM t_order_items
                WHERE m_store_id = %s
                  AND deleted_at IS NULL
                GROUP BY t_order_id
            ),
            valid_orders AS (
                SELECT
                    DATE(o.created_at AT TIME ZONE 'Asia/Jakarta') AS date,
                    o.id,
                    o.m_table_id,
                    o.m_menu_online_order_type_id,
                    COALESCE(oit.total_item_qty, 0)::numeric(15,2) AS total_item_qty
                FROM t_orders o
                LEFT JOIN order_item_totals oit ON oit.t_order_id = o.id
                WHERE o.m_store_id = %s
                  AND o.deleted_at IS NULL
                  AND o.cancelled_at IS NULL
                  AND COALESCE(o.m_order_status_id, 0) <> 3
                  AND (o.m_order_status_id = 2 OR o.m_order_payment_status_id = 200)
            ),
            order_estimates AS (
                SELECT
                    *,
                    CASE
                        WHEN m_menu_online_order_type_id IS NOT NULL THEN 0
                        WHEN total_item_qty <= 0 THEN 1
                        WHEN total_item_qty <= 3 THEN 1
                        WHEN total_item_qty <= 5 THEN 2
                        WHEN total_item_qty <= 8 THEN 3
                        ELSE 4
                    END::integer AS estimated_visitors
                FROM valid_orders
            )
            SELECT
                date,
                COALESCE(SUM(estimated_visitors), 0)::integer AS visitors,
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
                COALESCE(SUM(total_item_qty) FILTER (WHERE m_menu_online_order_type_id IS NULL), 0)::numeric(15,2) AS physical_item_qty,
                COALESCE(AVG(total_item_qty) FILTER (WHERE m_menu_online_order_type_id IS NULL), 0)::numeric(15,2) AS avg_physical_item_qty
            FROM order_estimates
            GROUP BY date
            ORDER BY date ASC
        """
        try:
            if conn is not None:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id, store_id))
                    return [dict(row) for row in cur.fetchall()]
            with self._connection() as owned_conn:
                with owned_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id, store_id))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f"DB error fetch_orders: {exc}")
            raise RuntimeError(f"Gagal mengambil t_orders/t_order_items dari database: {exc}") from exc

    def fetch_store_operational_hours(self, store_id: str, conn=None) -> List[Dict[str, Any]]:
        sql = """
            SELECT day_of_week, is_active, open_time, close_time
            FROM m_store_operational_hours
            WHERE m_store_id = %s
              AND deleted_at IS NULL
            ORDER BY day_of_week ASC
        """
        try:
            if conn is not None:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id,))
                    return [dict(row) for row in cur.fetchall()]
            with self._connection() as owned_conn:
                with owned_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f"DB error fetch_store_operational_hours: {exc}")
            raise RuntimeError(f"Gagal mengambil m_store_operational_hours dari database: {exc}") from exc

    def fetch_all_historical_data(self, store_id: str) -> Dict[str, List[Dict[str, Any]]]:
        try:
            with self._connection() as conn:
                orders = self.fetch_orders(store_id, conn=conn)
                operational_hours = self.fetch_store_operational_hours(store_id, conn=conn)
        except Exception as exc:
            logger.exception(f"DB error fetch_all_historical_data: {exc}")
            raise

        return {
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

        with self._connection() as conn:
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
                        %s, 'random forest', %s, 'visitors-backend-daily-history-v5',
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
    Preprocessor visitors versi orders + items_capped.

    Target dibuat dari t_orders valid non-online, lalu t_order_items.qty dipakai
    secara konservatif dengan cap per order:
    0-3 item = 1 visitor, 4-5 item = 2 visitors, 6-8 item = 3 visitors,
    >8 item = 4 visitors. Order online tetap 0 visitors fisik.
    """

    UNKNOWN_NUMERIC_COLUMNS = {
        "valid_orders_count",
        "physical_orders_count",
        "online_orders_count",
        "dine_in_orders_count",
        "takeaway_orders_count",
        "physical_item_qty",
        "avg_physical_item_qty",
        "avg_items_per_physical_order",
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
        return weekly[["date", "visitors"]].copy()

    def build_monthly_dataframe(self, raw_data: Dict[str, List[Dict]]) -> pd.DataFrame:
        df_daily = self.build_daily_dataframe(raw_data)
        if df_daily.empty:
            return pd.DataFrame()

        df_daily = df_daily.copy()
        df_daily["date"] = pd.to_datetime(df_daily["date"])
        df_daily = df_daily.set_index("date").sort_index()

        monthly = df_daily.resample("MS").sum(numeric_only=True)
        monthly = monthly.reset_index()
        return monthly[["date", "visitors"]].copy()

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
                    "valid_orders_count": 0,
                    "physical_orders_count": 0,
                    "online_orders_count": 0,
                    "dine_in_orders_count": 0,
                    "takeaway_orders_count": 0,
                    "physical_item_qty": 0.0,
                    "avg_physical_item_qty": 0.0,
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
                df["physical_item_qty"] = pd.to_numeric(df["physical_item_qty"], errors="coerce").fillna(0.0).clip(lower=0)
                df["avg_physical_item_qty"] = pd.to_numeric(df["avg_physical_item_qty"], errors="coerce").fillna(0.0).clip(lower=0)
                df = self._add_order_ratios(df)
                return df[[
                    "date",
                    "visitors",
                    "valid_orders_count",
                    "physical_orders_count",
                    "online_orders_count",
                    "dine_in_orders_count",
                    "takeaway_orders_count",
                    "physical_item_qty",
                    "avg_physical_item_qty",
                    "avg_items_per_physical_order",
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
            item_qty_col = next((c for c in ["total_item_qty", "totalItemQty", "item_qty", "itemQty", "qty"] if c in df.columns), None)

            if online_col:
                df["is_online"] = df[online_col].notna()
            else:
                df["is_online"] = False

            if table_col:
                df["is_dine_in"] = (~df["is_online"]) & df[table_col].notna()
            else:
                df["is_dine_in"] = False

            df["is_takeaway"] = (~df["is_online"]) & (~df["is_dine_in"])
            if item_qty_col:
                df["total_item_qty"] = pd.to_numeric(df[item_qty_col], errors="coerce").fillna(0.0).clip(lower=0)
            else:
                df["total_item_qty"] = 0.0

            def _estimate_visitors_from_item_qty(row: pd.Series) -> int:
                if bool(row.get("is_online", False)):
                    return 0
                qty = float(row.get("total_item_qty", 0.0) or 0.0)
                if qty <= 0:
                    return 1
                if qty <= 3:
                    return 1
                if qty <= 5:
                    return 2
                if qty <= 8:
                    return 3
                return 4

            df["estimated_visitors"] = df.apply(_estimate_visitors_from_item_qty, axis=1)
            df["physical_order_unit"] = (~df["is_online"]).astype(int)
            df["physical_item_qty_for_order"] = np.where(
                df["is_online"],
                0.0,
                pd.to_numeric(df["total_item_qty"], errors="coerce").fillna(0.0).clip(lower=0),
            )
            daily = df.groupby("date").agg(
                visitors=("estimated_visitors", "sum"),
                valid_orders_count=("estimated_visitors", "count"),
                physical_orders_count=("physical_order_unit", "sum"),
                online_orders_count=("is_online", "sum"),
                dine_in_orders_count=("is_dine_in", "sum"),
                takeaway_orders_count=("is_takeaway", "sum"),
                physical_item_qty=("physical_item_qty_for_order", "sum"),
                avg_physical_item_qty=("physical_item_qty_for_order", lambda x: float(pd.to_numeric(x, errors="coerce").fillna(0.0).sum() / max((x > 0).sum(), 1))),
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
        physical_denominator = df["physical_orders_count"].replace(0, np.nan)
        if "physical_item_qty" in df.columns:
            df["avg_items_per_physical_order"] = (df["physical_item_qty"] / physical_denominator).fillna(0.0)
        else:
            df["avg_items_per_physical_order"] = 0.0
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


        # Lag/rolling untuk item/order-derived metrics aman karena hanya memakai histori masa lalu.
        for item_col in ["physical_item_qty", "avg_physical_item_qty", "avg_items_per_physical_order"]:
            if item_col in df.columns:
                df[f"lag_{item_col}_7"] = df[item_col].shift(7)
                df[f"rolling_{item_col}_7"] = df[item_col].shift(1).rolling(7, min_periods=1).mean()

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
            "valid_orders_count",
            "physical_orders_count",
            "online_orders_count",
            "dine_in_orders_count",
            "takeaway_orders_count",
            "physical_item_qty",
            "avg_physical_item_qty",
            "avg_items_per_physical_order",
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


        for item_col in ["physical_item_qty", "avg_physical_item_qty", "avg_items_per_physical_order"]:
            if item_col in history.columns:
                hist_item = pd.to_numeric(history[item_col], errors="coerce").fillna(0).values
                row[f"lag_{item_col}_7"] = float(hist_item[-7]) if len(hist_item) >= 7 else 0.0
                recent_item = hist_item[-7:] if len(hist_item) >= 7 else hist_item
                row[f"rolling_{item_col}_7"] = float(np.mean(recent_item)) if len(recent_item) > 0 else 0.0
            else:
                row[f"lag_{item_col}_7"] = 0.0
                row[f"rolling_{item_col}_7"] = 0.0

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
        self.feature_version = "visitors-backend-daily-history-v5"
        self.data_source = "backend_visitors_daily_history_aggregated_from_t_orders_t_order_items_operational_hours"

    def _tag_model_metadata(self, store_id: str, meta: Dict[str, Any], granularity: str = "daily") -> Dict[str, Any]:
        meta = dict(meta or {})
        meta["feature_version"] = self.feature_version
        meta["data_source"] = self.data_source
        meta["target_definition"] = "SUM(items_capped visitors for valid non-online t_orders; online orders = 0)"
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


    def _round_metric(self, value: Any, digits: int = 4) -> Optional[float]:
        if value is None:
            return None
        try:
            val = float(value)
            if not np.isfinite(val):
                return None
            return round(val, digits)
        except Exception:
            return None

    def _classify_reliability(self, error_ratio: Optional[float]) -> Optional[str]:
        """
        error_ratio disimpan sebagai rasio 0..1.
        Batas ini sengaja sederhana agar mudah ditampilkan di frontend.
        """
        if error_ratio is None:
            return None
        if error_ratio <= 0.10:
            return "high"
        if error_ratio <= 0.20:
            return "medium"
        if error_ratio <= 0.30:
            return "low_medium"
        return "low"

    def _metric_block(self, prefix: str, actual: np.ndarray, predicted: np.ndarray) -> Dict[str, Any]:
        actual = np.asarray(actual, dtype=float)
        predicted = np.asarray(predicted, dtype=float)
        if len(actual) == 0 or len(predicted) == 0:
            return {
                f"{prefix}_metric_available": False,
                f"{prefix}_mae": None,
                f"{prefix}_rmse": None,
                f"{prefix}_mae_percentage": None,
                f"{prefix}_error_ratio": None,
                f"{prefix}_reliability": None,
            }

        mae = float(mean_absolute_error(actual, predicted))
        rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
        baseline = float(np.mean(np.abs(actual)))
        if baseline <= 0:
            error_ratio = None
            mae_percentage = None
        else:
            error_ratio = mae / baseline
            mae_percentage = error_ratio * 100.0

        return {
            f"{prefix}_metric_available": True,
            f"{prefix}_mae": self._round_metric(mae),
            f"{prefix}_rmse": self._round_metric(rmse),
            f"{prefix}_mae_percentage": self._round_metric(mae_percentage, 2),
            f"{prefix}_error_ratio": self._round_metric(error_ratio, 4),
            f"{prefix}_reliability": self._classify_reliability(error_ratio),
        }

    def _aggregate_oos_metric(self, oos_df: pd.DataFrame, horizon: str) -> Dict[str, Any]:
        if oos_df.empty:
            return self._metric_block(horizon, np.array([]), np.array([]))

        df = oos_df.copy()
        df["date"] = pd.to_datetime(df["date"])

        if horizon == "weekly":
            df["period_start"] = df["date"].dt.to_period("W-SUN").apply(lambda p: p.start_time.date())
            grouped = df.groupby("period_start").agg(
                actual=("actual", "sum"),
                predicted=("predicted", "sum"),
                days=("date", "count"),
            ).reset_index()
            # Hanya nilai minggu penuh agar metric weekly tidak tercampur minggu parsial.
            grouped = grouped[grouped["days"] >= 7]
            return self._metric_block("weekly", grouped["actual"].values, grouped["predicted"].values)

        if horizon == "monthly":
            df["period"] = df["date"].dt.to_period("M")
            grouped = df.groupby("period").agg(
                actual=("actual", "sum"),
                predicted=("predicted", "sum"),
                days=("date", "count"),
            ).reset_index()
            grouped["expected_days"] = grouped["period"].apply(lambda p: int(p.days_in_month))
            # Hanya bulan penuh agar monthly MAE/RMSE benar-benar metric bulanan.
            grouped = grouped[grouped["days"] >= grouped["expected_days"]]
            return self._metric_block("monthly", grouped["actual"].values, grouped["predicted"].values)

        return self._metric_block(horizon, np.array([]), np.array([]))

    def _build_oos_daily_predictions(
        self,
        df_features: pd.DataFrame,
        feature_cols: List[str],
    ) -> pd.DataFrame:
        """
        Membuat out-of-sample prediction dari TimeSeriesSplit.
        Ini dipakai supaya weekly/monthly metrics dihitung dari prediksi daily historis
        yang diagregasi, bukan sekadar menyalin metric daily model.
        """
        if df_features.empty or len(df_features) < 40:
            return pd.DataFrame(columns=["date", "actual", "predicted"])

        X = df_features[feature_cols].values
        y = df_features["visitors"].values.astype(float)
        dates = pd.to_datetime(df_features["date"])

        n_splits = min(5, max(2, len(df_features) // 30))
        try:
            tscv = TimeSeriesSplit(n_splits=n_splits)
        except Exception:
            return pd.DataFrame(columns=["date", "actual", "predicted"])

        rows: List[Dict[str, Any]] = []
        for train_idx, val_idx in tscv.split(X):
            if len(train_idx) < 20 or len(val_idx) == 0:
                continue

            scaler = StandardScaler()
            X_train = scaler.fit_transform(X[train_idx])
            X_val = scaler.transform(X[val_idx])
            y_train = y[train_idx]
            y_val = y[val_idx]

            fold_model = RandomForestRegressor(
                n_estimators=200,
                max_depth=12,
                min_samples_split=5,
                min_samples_leaf=2,
                max_features="sqrt",
                bootstrap=True,
                random_state=42,
                n_jobs=-1,
            )
            fold_model.fit(X_train, y_train)
            y_pred = np.maximum(fold_model.predict(X_val), 0)

            for dt, actual, predicted in zip(dates.iloc[val_idx], y_val, y_pred):
                rows.append({
                    "date": dt,
                    "actual": float(actual),
                    "predicted": float(predicted),
                })

        if not rows:
            return pd.DataFrame(columns=["date", "actual", "predicted"])
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    def _calculate_horizon_metrics(
        self,
        *,
        store_id: str,
        meta: Dict[str, Any],
        raw_data: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """Hitung metric daily, weekly, monthly berbasis out-of-sample backtest."""
        if raw_data is None:
            # Jangan buka koneksi PostgreSQL langsung dari path metadata.
            # Weekly/monthly biasanya sudah memakai horizon_metrics yang tersimpan
            # dari daily forecast sebelumnya. Jika belum ada, kembalikan kosong.
            return dict(meta.get("horizon_metrics") or {})
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)
        if df_daily.empty:
            return {}

        df_features = self.preprocessor.engineer_features(df_daily)
        feature_cols = self.preprocessor.get_feature_columns(df_features)
        oos_df = self._build_oos_daily_predictions(df_features, feature_cols)

        metrics: Dict[str, Any] = {
            "metrics_version": "horizon-aware-oos-v1",
            "metric_source": "time_series_split_oos_daily_predictions",
            "metric_note": (
                "weekly/monthly metrics are calculated by aggregating out-of-sample daily "
                "predictions into complete weekly/monthly periods."
            ),
            "daily_training_rows_before_features": int(len(df_daily)),
            "daily_training_data_points": int(len(df_features)),
            "oos_daily_prediction_points": int(len(oos_df)),
        }

        if not oos_df.empty:
            metrics.update(self._metric_block("daily", oos_df["actual"].values, oos_df["predicted"].values))
            metrics.update(self._aggregate_oos_metric(oos_df, "weekly"))
            metrics.update(self._aggregate_oos_metric(oos_df, "monthly"))
        else:
            metrics.update(self._metric_block("daily", np.array([]), np.array([])))
            metrics.update(self._metric_block("weekly", np.array([]), np.array([])))
            metrics.update(self._metric_block("monthly", np.array([]), np.array([])))

        # Fallback: kalau OOS daily tidak tersedia, tetap isi daily dari meta lama.
        if not metrics.get("daily_metric_available") and meta.get("cv_mae") is not None:
            avg_actual = float(df_features["visitors"].mean()) if not df_features.empty else 0.0
            mae = float(meta.get("cv_mae", 0.0))
            rmse = float(meta.get("cv_rmse", 0.0))
            ratio = mae / avg_actual if avg_actual > 0 else None
            metrics.update({
                "daily_metric_available": True,
                "daily_mae": self._round_metric(mae),
                "daily_rmse": self._round_metric(rmse),
                "daily_mae_percentage": self._round_metric(ratio * 100 if ratio is not None else None, 2),
                "daily_error_ratio": self._round_metric(ratio, 4),
                "daily_reliability": self._classify_reliability(ratio),
                "metric_source": "trainer_cv_fallback",
            })

        return metrics

    def _horizon_method(self, horizon_label: str) -> str:
        if horizon_label == "daily":
            return "direct_daily_model"
        if horizon_label == "weekly":
            return "aggregated_from_daily_forecast_weekly_backtest_metric"
        if horizon_label == "monthly":
            return "aggregated_from_daily_forecast_monthly_backtest_metric"
        return "unknown"

    def _metadata_for_response(
        self,
        *,
        store_id: str,
        meta: Dict[str, Any],
        horizon_label: str,
        raw_data: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> ModelMetadata:
        metrics = dict(meta.get("horizon_metrics") or {})
        if metrics.get("metrics_version") != "horizon-aware-oos-v1":
            metrics = self._calculate_horizon_metrics(store_id=store_id, meta=meta, raw_data=raw_data)
            meta["horizon_metrics"] = metrics
            try:
                meta_path = trainer._meta_path(store_id, "daily")
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2)
            except Exception as exc:
                logger.warning(f"Gagal menyimpan horizon-aware metrics visitors: {exc}")

        selected_mae = metrics.get(f"{horizon_label}_mae")
        selected_rmse = metrics.get(f"{horizon_label}_rmse")
        if selected_mae is None:
            selected_mae = metrics.get("daily_mae", meta.get("cv_mae"))
        if selected_rmse is None:
            selected_rmse = metrics.get("daily_rmse", meta.get("cv_rmse"))

        selected_metrics: Dict[str, Any] = {
            "metrics_version": metrics.get("metrics_version"),
            "metric_source": metrics.get("metric_source"),
            "training_rows_before_features": metrics.get("daily_training_rows_before_features"),
            "training_data_points": metrics.get("daily_training_data_points"),
            "oos_prediction_points": metrics.get("oos_daily_prediction_points"),
            f"{horizon_label}_metric_available": bool(metrics.get(f"{horizon_label}_metric_available", False)),
            f"{horizon_label}_mae": metrics.get(f"{horizon_label}_mae"),
            f"{horizon_label}_rmse": metrics.get(f"{horizon_label}_rmse"),
            f"{horizon_label}_mae_percentage": metrics.get(f"{horizon_label}_mae_percentage"),
            f"{horizon_label}_error_ratio": metrics.get(f"{horizon_label}_error_ratio"),
            f"{horizon_label}_reliability": metrics.get(f"{horizon_label}_reliability"),
        }
        selected_metrics = {k: v for k, v in selected_metrics.items() if v is not None}

        # Metric horizon aktif hanya ditaruh di model_metadata.metrics.
        # Jangan duplikasi ke top-level model_metadata agar response lebih bersih.
        return ModelMetadata(
            trained_at=datetime.fromisoformat(meta["trained_at"]) if meta.get("trained_at") else None,
            training_data_points=int(meta.get("training_data_points", 0)),
            feature_importance=meta.get("top_features", meta.get("feature_importance", {})),
            cv_mae=self._round_metric(selected_mae),
            cv_rmse=self._round_metric(selected_rmse),
            horizon_method=self._horizon_method(horizon_label),
            metric_horizon=horizon_label,
            metrics=selected_metrics,
        )

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
        raw_data = asyncio.run(golang_client.fetch_all_historical_data(store_id))
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
        metadata_metrics = dict(getattr(metadata, "metrics", {}) or {})
        mae_value = metadata_metrics.get(f"{horizon_label}_mae", getattr(metadata, "cv_mae", None))
        rmse_value = metadata_metrics.get(f"{horizon_label}_rmse", getattr(metadata, "cv_rmse", None))
        mae = float(mae_value or 0.0)
        rmse = float(rmse_value or 0.0)
        mape = None
        model_version = "visitors-rf-v3-items-capped"

        avg_prediction = max(
            1.0,
            float(np.mean([max(0, item.predicted_visitors) for item in forecasts])),
        )
        # Untuk confidence hasil forecast saat ini, error ratio dihitung terhadap
        # rata-rata predicted value horizon aktif. Metadata model tetap memakai
        # mae_percentage/error_ratio terhadap actual backtest.
        forecast_error_ratio = min(1.0, mae / avg_prediction) if mae > 0 else 0.0
        confidence_level = int(max(0, min(100, round(100.0 - forecast_error_ratio * 100.0))))

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

        selected_error_ratio = metadata_metrics.get(f"{horizon_label}_error_ratio")
        selected_mae_percentage = metadata_metrics.get(f"{horizon_label}_mae_percentage")
        selected_reliability = metadata_metrics.get(f"{horizon_label}_reliability")

        metrics = {
            "horizon_method": getattr(metadata, "horizon_method", None),
            "metric_horizon": horizon_label,
            "mae": mae,  # legacy selected horizon MAE
            "rmse": rmse,  # legacy selected horizon RMSE
            "mape": mape,
            "confidence_level": confidence_level,
            "forecast_error_ratio": round(forecast_error_ratio, 4),
            f"{horizon_label}_mae": mae,
            f"{horizon_label}_rmse": rmse,
            f"{horizon_label}_mae_percentage": selected_mae_percentage,
            f"{horizon_label}_error_ratio": selected_error_ratio,
            f"{horizon_label}_reliability": selected_reliability,
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
        raw_data = await golang_client.fetch_all_historical_data(store_id)
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
        raw_data = await golang_client.fetch_all_historical_data(store_id)
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
            for channel_col in ["online_ratio", "dine_in_ratio", "takeaway_ratio"]:
                if channel_col in running_history.columns:
                    new_history[channel_col] = float(row.get(f"rolling_{channel_col}_7", 0.0))
            running_history = pd.concat([running_history, pd.DataFrame([new_history])], ignore_index=True)

        return ForecastResponse(
            store_id=store_id,
            generated_at=datetime.utcnow(),
            forecast_horizon_days=forecast_days,
            forecasts=forecasts,
            model_metadata=self._metadata_for_response(
                store_id=store_id,
                meta=meta,
                horizon_label="daily",
                raw_data=raw_data,
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
        raw_data = await golang_client.fetch_all_historical_data(store_id)
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
        raw_data = await golang_client.fetch_all_historical_data(store_id)
        
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
            model_metadata=self._metadata_for_response(
                store_id=store_id,
                meta=trainer.load_model(store_id)[3],
                horizon_label="weekly",
            ),
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
            model_metadata=self._metadata_for_response(
                store_id=store_id,
                meta=trainer.load_model(store_id)[3],
                horizon_label="monthly",
            ),
            status="success",
            message=(
                f"Berhasil memprediksi {forecast_months} bulan ke depan "
                "dari agregasi daily forecast"
            ),
        )

forecast_service = ForecastService()
