"""
app/services/db_client.py
Postgres client untuk mengambil data historis langsung dari database.
"""
from typing import List, Dict, Any

import psycopg2
import psycopg2.extras

from modules.visitors.app.utils.config import settings
from modules.visitors.app.utils.logger import logger


class PostgresClient:
    """
    Client sederhana untuk query data historis dari Postgres.
    """

    def __init__(self) -> None:
        pass

    def _validate_config(self) -> None:
        missing = [
            name for name, value in {
                "DB_HOST": settings.db_host,
                "DB_PORT": settings.db_port,
                "DB_USER": settings.db_user,
                "DB_PASSWORD": settings.db_password,
                "DB_NAME": settings.db_name,
            }.items() if not value
        ]
        if missing:
            raise ValueError(
                "Database config tidak lengkap. Missing env: " + ", ".join(missing)
            )

    def _connect(self):
        self._validate_config()
        return psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            dbname=settings.db_name,
            sslmode=settings.db_sslmode,
        )

    def fetch_sales_daily_summaries(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Ambil data t_sales_daily_summaries untuk satu store.
        """
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
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"DB error fetch_sales_daily_summaries: {exc}")
            return []

    def fetch_orders(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Ambil data t_orders untuk satu store (fallback jika sales_daily kosong).
        """
        sql = """
            SELECT id, created_at, total_price
            FROM t_orders
            WHERE m_store_id = %s AND deleted_at IS NULL
            ORDER BY created_at ASC
        """
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql, (store_id,))
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"DB error fetch_orders: {exc}")
            return []

    def fetch_all_historical_data(self, store_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Ambil semua data historis yang dibutuhkan untuk forecasting.
        """
        daily = self.fetch_sales_daily_summaries(store_id)
        orders = self.fetch_orders(store_id)
        return {
            "sales_daily": daily,
            "sales_monthly": [],
            "orders": orders,
        }


# Singleton instance
db_client = PostgresClient()
