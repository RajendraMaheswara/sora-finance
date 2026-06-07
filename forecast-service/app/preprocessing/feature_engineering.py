"""
app/preprocessing/feature_engineering.py
Preprocessing pipeline dan feature engineering untuk Random Forest.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from datetime import datetime, date

from app.utils.logger import logger


HARI_INDONESIA = {
    0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis",
    4: "Jumat", 5: "Sabtu", 6: "Minggu"
}


class VisitorPreprocessor:
    """
    Mengolah data mentah dari Golang API menjadi fitur siap pakai
    untuk model Random Forest.
    """

    def build_daily_dataframe(
        self, raw_data: Dict[str, List[Dict]]
    ) -> pd.DataFrame:
        """
        Bangun DataFrame harian dari data mentah API.
        Prioritas: sales_daily_summaries → fallback ke orders.
        """
        df = self._build_from_sales_daily(raw_data.get("sales_daily", []))

        if df.empty:
            logger.warning("sales_daily kosong, fallback ke data orders")
            df = self._build_from_orders(raw_data.get("orders", []))

        if df.empty:
            logger.error("Tidak ada data historis yang bisa digunakan")
            return pd.DataFrame()

        df = df.sort_values("date").reset_index(drop=True)
        logger.info(f"DataFrame harian: {len(df)} baris, rentang {df['date'].min()} - {df['date'].max()}")
        return df

    def build_weekly_dataframe(
        self, raw_data: Dict[str, List[Dict]]
    ) -> pd.DataFrame:
        """
        Bangun DataFrame mingguan dari data harian.
        Week start = Senin, week end = Minggu.
        """
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

    def build_monthly_dataframe(
        self, raw_data: Dict[str, List[Dict]]
    ) -> pd.DataFrame:
        """
        Bangun DataFrame bulanan dari data harian.
        """
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
        if not records:
            return pd.DataFrame()
        try:
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["total_transaction"] = pd.to_numeric(
                df.get("total_transaction", df.get("totalTransaction", 0)),
                errors="coerce"
            ).fillna(0).astype(int)
            df["total_omzet"] = pd.to_numeric(
                df.get("total_omzet", df.get("totalOmzet", 0)),
                errors="coerce"
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
            date_col = next(
                (c for c in ["created_at", "createdAt", "date"] if c in df.columns), None
            )
            if not date_col:
                return pd.DataFrame()
            df["date"] = pd.to_datetime(df[date_col]).dt.date
            daily = df.groupby("date").agg(
                visitors=("id", "count"),
                omzet=("total_price", lambda x: pd.to_numeric(x, errors="coerce").sum())
            ).reset_index()
            return daily
        except Exception as e:
            logger.error(f"Error parsing orders: {e}")
            return pd.DataFrame()

    def engineer_features(
        self,
        df: pd.DataFrame,
        lags: List[int] | None = None,
        windows: List[int] | None = None,
        expanding_min_periods: int | None = None,
    ) -> pd.DataFrame:
        """
        Feature engineering lengkap untuk Random Forest.
        lags/windows bisa disesuaikan untuk periode mingguan/bulanan.
        """
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        lags = lags or [1, 2, 3, 7, 14, 21, 28]
        windows = windows or [7, 14, 28]
        max_lag = max(lags)
        expanding_min_periods = expanding_min_periods or max(7, min(windows))

        # ── Fitur Kalender ─────────────────────────────
        df["day_of_week"] = df["date"].dt.dayofweek          # 0=Senin, 6=Minggu
        df["day_of_month"] = df["date"].dt.day
        df["month"] = df["date"].dt.month
        df["quarter"] = df["date"].dt.quarter
        df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        df["is_month_start"] = df["date"].dt.is_month_start.astype(int)
        df["is_month_end"] = df["date"].dt.is_month_end.astype(int)

        # ── Fitur Siklik (sin/cos) ─────────────────────
        df["sin_dow"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["cos_dow"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
        df["sin_month"] = np.sin(2 * np.pi * df["month"] / 12)
        df["cos_month"] = np.cos(2 * np.pi * df["month"] / 12)

        # ── Lag Features ───────────────────────────────
        for lag in lags:
            df[f"lag_{lag}"] = df["visitors"].shift(lag)

        # ── Rolling Statistics ─────────────────────────
        for window in windows:
            df[f"rolling_mean_{window}"] = (
                df["visitors"].shift(1).rolling(window=window, min_periods=1).mean()
            )
            df[f"rolling_std_{window}"] = (
                df["visitors"].shift(1).rolling(window=window, min_periods=1).std().fillna(0)
            )
            df[f"rolling_max_{window}"] = (
                df["visitors"].shift(1).rolling(window=window, min_periods=1).max()
            )
            df[f"rolling_min_{window}"] = (
                df["visitors"].shift(1).rolling(window=window, min_periods=1).min()
            )

        # ── Expanding Mean (tren jangka panjang) ───────
        df["expanding_mean"] = (
            df["visitors"].shift(1).expanding(min_periods=expanding_min_periods).mean()
        )

        # ── Omzet per Visitor (jika tersedia) ──────────
        if "omzet" in df.columns:
            df["omzet_per_visitor"] = (
                df["omzet"] / df["visitors"].replace(0, np.nan)
            ).fillna(0)
            df["lag_omzet_7"] = df["omzet"].shift(7)
            df["rolling_omzet_7"] = (
                df["omzet"].shift(1).rolling(7, min_periods=1).mean()
            )

        # Drop baris dengan terlalu banyak NaN (lag paling jauh = 28)
        df = df.dropna(subset=[f"lag_{max_lag}"]).reset_index(drop=True)

        logger.info(f"Feature engineering selesai: {len(df)} baris, {len(df.columns)} kolom")
        return df

    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """
        Kembalikan daftar kolom fitur (bukan target, bukan metadata).
        """
        exclude = {"date", "visitors", "omzet"}
        return [c for c in df.columns if c not in exclude]

    def prepare_future_features(
        self,
        df_history: pd.DataFrame,
        forecast_days: int,
        start_date: date,
        lags: List[int] | None = None,
        windows: List[int] | None = None,
    ) -> pd.DataFrame:
        """
        Buat DataFrame fitur untuk hari-hari yang akan diprediksi.
        Menggunakan rolling windows berbasis data historis + prediksi sebelumnya.
        """
        future_dates = pd.date_range(
            start=start_date, periods=forecast_days, freq="D"
        )
        history = df_history[["date", "visitors"]].copy()
        history["date"] = pd.to_datetime(history["date"])

        future_rows = []
        for future_date in future_dates:
            row = self._build_future_row(future_date, history, lags=lags, windows=windows)
            future_rows.append(row)
            # Setelah prediksi, tambahkan ke history (akan diisi saat predict loop)
            # Di sini kita tambahkan placeholder, nanti diisi service
            history = pd.concat([
                history,
                pd.DataFrame([{"date": future_date, "visitors": 0}])
            ], ignore_index=True)

        return pd.DataFrame(future_rows)

    def _build_future_row(
        self,
        target_date: pd.Timestamp,
        history: pd.DataFrame,
        lags: List[int] | None = None,
        windows: List[int] | None = None,
    ) -> Dict[str, Any]:
        """
        Bangun satu baris fitur untuk tanggal target.
        """
        row: Dict[str, Any] = {}
        lags = lags or [1, 2, 3, 7, 14, 21, 28]
        windows = windows or [7, 14, 28]

        # Kalender
        row["day_of_week"] = target_date.dayofweek
        row["day_of_month"] = target_date.day
        row["month"] = target_date.month
        row["quarter"] = target_date.quarter
        row["week_of_year"] = target_date.isocalendar()[1]
        row["is_weekend"] = int(target_date.dayofweek in [5, 6])
        row["is_month_start"] = int(target_date.is_month_start)
        row["is_month_end"] = int(target_date.is_month_end)

        # Siklik
        row["sin_dow"] = np.sin(2 * np.pi * row["day_of_week"] / 7)
        row["cos_dow"] = np.cos(2 * np.pi * row["day_of_week"] / 7)
        row["sin_month"] = np.sin(2 * np.pi * row["month"] / 12)
        row["cos_month"] = np.cos(2 * np.pi * row["month"] / 12)

        # Lag dari history
        hist_visitors = history["visitors"].values
        for lag in lags:
            idx = len(hist_visitors) - lag
            row[f"lag_{lag}"] = float(hist_visitors[idx]) if idx >= 0 else 0.0

        # Rolling stats
        for window in windows:
            recent = hist_visitors[-window:] if len(hist_visitors) >= window else hist_visitors
            row[f"rolling_mean_{window}"] = float(np.mean(recent)) if len(recent) > 0 else 0.0
            row[f"rolling_std_{window}"] = float(np.std(recent)) if len(recent) > 1 else 0.0
            row[f"rolling_max_{window}"] = float(np.max(recent)) if len(recent) > 0 else 0.0
            row[f"rolling_min_{window}"] = float(np.min(recent)) if len(recent) > 0 else 0.0

        row["expanding_mean"] = float(np.mean(hist_visitors)) if len(hist_visitors) > 0 else 0.0

        # Omzet features (placeholder jika tidak ada)
        row["omzet_per_visitor"] = 0.0
        row["lag_omzet_7"] = 0.0
        row["rolling_omzet_7"] = 0.0

        row["date"] = target_date
        return row
