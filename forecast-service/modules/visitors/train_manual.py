"""
train_manual.py
Script training mandiri — bisa dijalankan dari terminal tanpa menghidupkan server.

Usage:
    python train_manual.py --store_id <UUID>
    python train_manual.py --store_id <UUID> --use_dummy   # gunakan data dummy untuk testing
"""
import asyncio
import argparse
import pandas as pd
import numpy as np
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from modules.visitors.app.services.golang_client import golang_client
from modules.visitors.app.preprocessing.feature_engineering import VisitorPreprocessor
from modules.visitors.app.training.trainer import trainer
from modules.visitors.app.utils.logger import logger


def generate_dummy_data(n_days: int = 365) -> dict:
    """
    Buat data dummy yang realistis untuk testing offline.
    Pola: weekday lebih sepi dari weekend, ada tren musiman.
    """
    np.random.seed(42)
    dates = [date.today() - timedelta(days=n_days - i) for i in range(n_days)]
    records = []
    for d in dates:
        base = 80
        dow_effect = 30 if d.weekday() in [5, 6] else 0  # ramai di weekend
        month_effect = 10 * np.sin(2 * np.pi * d.month / 12)
        noise = np.random.normal(0, 10)
        visitors = max(5, int(base + dow_effect + month_effect + noise))

        records.append({
            "date": d.isoformat(),
            "total_transaction": visitors,
            "total_omzet": visitors * np.random.uniform(25000, 45000),
        })
    return {"sales_daily": records, "sales_monthly": [], "orders": []}


async def train_for_store(store_id: str, use_dummy: bool = False):
    preprocessor = VisitorPreprocessor()

    if use_dummy:
        logger.info("Menggunakan data dummy (mode testing)")
        raw_data = generate_dummy_data(365)
    else:
        logger.info(f"Mengambil data dari Golang API untuk store: {store_id}")
        raw_data = await golang_client.fetch_all_historical_data(store_id)

    df_daily = preprocessor.build_daily_dataframe(raw_data)
    if df_daily.empty:
        logger.error("Tidak ada data. Pastikan store memiliki transaksi atau gunakan --use_dummy")
        return

    logger.info(f"Data harian: {len(df_daily)} baris")
    logger.info(f"Rentang tanggal: {df_daily['date'].min()} s.d. {df_daily['date'].max()}")
    logger.info(f"Rata-rata pengunjung per hari: {df_daily['visitors'].mean():.1f}")

    df_features = preprocessor.engineer_features(df_daily)
    feature_cols = preprocessor.get_feature_columns(df_features)

    logger.info(f"Jumlah fitur: {len(feature_cols)}")
    logger.info(f"Contoh fitur: {feature_cols[:5]}...")

    meta = trainer.train(df_features, feature_cols, store_id)

    print("\n" + "=" * 50)
    print("  TRAINING SELESAI")
    print("=" * 50)
    print(f"  Store ID     : {store_id}")
    print(f"  Data Points  : {meta['training_data_points']}")
    print(f"  CV MAE       : {meta['cv_mae']:.2f} pengunjung")
    print(f"  CV RMSE      : {meta['cv_rmse']:.2f} pengunjung")
    print(f"  Trained At   : {meta['trained_at']}")
    print("\n  Top 5 Fitur Terpenting:")
    top5 = sorted(meta["feature_importance"].items(), key=lambda x: x[1], reverse=True)[:5]
    for feat, imp in top5:
        bar = "█" * int(imp * 50)
        print(f"    {feat:<30} {imp:.4f} {bar}")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual training script Sora Forecast Service")
    parser.add_argument("--store_id", type=str, required=True, help="UUID store")
    parser.add_argument(
        "--use_dummy", action="store_true",
        help="Gunakan data dummy (untuk testing offline)"
    )
    args = parser.parse_args()

    asyncio.run(train_for_store(args.store_id, args.use_dummy))
