"""
app/services/golang_client.py
Async HTTP client untuk mengambil data historis dari Golang API.
"""
import httpx
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.utils.config import settings
from app.utils.logger import logger


class GolangAPIClient:
    """
    Async client untuk Golang REST API.
    Mengambil data orders dan sales summaries untuk feature engineering.
    """

    def __init__(self):
        self.base_url = settings.golang_api_base_url.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """
        Generic async GET request dengan retry logic.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params)
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
        """
        Health check ke Golang API.
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/stores")
                return response.status_code < 500
        except Exception:
            return False

    async def fetch_sales_daily_summaries(
        self, store_id: str
    ) -> List[Dict]:
        """
        Ambil data t_sales_daily_summaries untuk satu store.
        Endpoint: GET /api/sales-daily-summaries?store_id={store_id}
        """
        logger.info(f"Fetching sales daily summaries for store {store_id}")
        try:
            data = await self._get("sales-daily-summaries", params={"store_id": store_id})
            # Handle berbagai format response (list langsung atau wrapped)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("data", data.get("items", []))
            return []
        except Exception as e:
            logger.error(f"Failed to fetch sales daily summaries: {e}")
            return []

    async def fetch_sales_monthly_summaries(
        self, store_id: str
    ) -> List[Dict]:
        """
        Ambil data t_sales_monthly_summaries untuk satu store.
        """
        logger.info(f"Fetching sales monthly summaries for store {store_id}")
        try:
            data = await self._get(
                "sales-monthly-summaries", params={"store_id": store_id}
            )
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("data", data.get("items", []))
            return []
        except Exception as e:
            logger.error(f"Failed to fetch sales monthly summaries: {e}")
            return []

    async def fetch_orders(self, store_id: str) -> List[Dict]:
        """
        Ambil data t_orders untuk satu store.
        """
        logger.info(f"Fetching orders for store {store_id}")
        try:
            data = await self._get("orders", params={"store_id": store_id})
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("data", data.get("items", []))
            return []
        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            return []

    async def fetch_all_historical_data(
        self, store_id: str
    ) -> Dict[str, List[Dict]]:
        """
        Ambil semua data historis secara concurrent untuk efisiensi.
        """
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


# Singleton instance
golang_client = GolangAPIClient()
