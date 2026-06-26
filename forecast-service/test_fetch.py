import asyncio
from modules.sales.forecaster import GolangAPIClient

async def main():
    client = GolangAPIClient()
    res = await client.fetch_sales_daily_summaries("47dad341-000e-45af-81db-7644864b5ae4")
    print(res[:2] if res else "No data")

asyncio.run(main())
