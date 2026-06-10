"""
app/services/forecast_service.py
Business logic: orchestrate data fetching, preprocessing, training, dan prediction.
"""
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, Any

from app.services.golang_client import golang_client
from app.services.db_client import db_client
from app.preprocessing.feature_engineering import VisitorPreprocessor, HARI_INDONESIA
from app.training.trainer import trainer
from app.models.schemas import (
    ForecastResponse, DailyForecast, ModelMetadata,
    WeeklyForecastResponse, WeeklyForecast,
    MonthlyForecastResponse, MonthlyForecast,
    RetrainResponse,
)
from app.utils.logger import logger


class ForecastService:
    """
    Orchestrator utama: ambil data → preprocess → train/load model → predict.
    """

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

    # ─────────────────────────────────────────────────────────────
    # RETRAIN
    # ─────────────────────────────────────────────────────────────

    async def retrain(self, store_id: str, force: bool = False) -> RetrainResponse:
        """
        Ambil data terbaru, lakukan feature engineering, lalu latih ulang model.
        """
        logger.info(f"[RETRAIN] store={store_id}, force={force}")

        # Ambil data historis dari Golang API
        raw_data = await golang_client.fetch_all_historical_data(store_id)

        df_daily = self.preprocessor.build_daily_dataframe(raw_data)
        if df_daily.empty:
            raise ValueError(
                f"Tidak ada data historis untuk store {store_id}. "
                "Pastikan store sudah memiliki transaksi."
            )

        if len(df_daily) < 30:
            raise ValueError(
                f"Data historis terlalu sedikit: {len(df_daily)} hari. "
                "Minimal dibutuhkan 30 hari data."
            )

        # Feature engineering
        df_features = self.preprocessor.engineer_features(df_daily)
        feature_cols = self.preprocessor.get_feature_columns(df_features)

        # Training
        meta = trainer.train(df_features, feature_cols, store_id)

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

    # ─────────────────────────────────────────────────────────────
    # PREDICT
    # ─────────────────────────────────────────────────────────────

    async def forecast(
        self,
        store_id: str,
        forecast_days: int,
        start_date: date,
    ) -> ForecastResponse:
        """
        Load model, buat fitur masa depan, lakukan prediksi.
        """
        logger.info(f"[FORECAST] store={store_id}, days={forecast_days}, start={start_date}")

        # Auto-retrain jika model belum ada
        if not trainer.model_exists(store_id):
            logger.info(f"Model belum ada untuk store {store_id}, auto-training...")
            await self.retrain(store_id)

        # Load model
        model, scaler, feature_cols, meta = trainer.load_model(store_id)

        # Ambil data historis untuk membangun lag/rolling features masa depan
        raw_data = await golang_client.fetch_all_historical_data(store_id)
        df_daily = self.preprocessor.build_daily_dataframe(raw_data)

        if df_daily.empty:
            raise ValueError(f"Tidak ada data historis untuk store {store_id}")

        # Hitung std historis untuk confidence interval
        hist_std = float(df_daily["visitors"].std()) if len(df_daily) > 1 else 5.0
        ci_multiplier = 1.28  # ~80% CI

        # Prediksi iteratif (setiap hari menggunakan prediksi hari sebelumnya)
        forecasts = []
        running_history = df_daily[["date", "visitors"]].copy()
        running_history["date"] = pd.to_datetime(running_history["date"])

        for day_offset in range(forecast_days):
            target_date = pd.Timestamp(start_date) + timedelta(days=day_offset)

            # Bangun fitur untuk hari ini
            row = self.preprocessor._build_future_row(target_date, running_history)
            # Pastikan urutan kolom sesuai training
            X_row = np.array([[row.get(col, 0.0) for col in feature_cols]])
            X_scaled = scaler.transform(X_row)

            # Prediksi dari semua pohon untuk dapatkan distribusi
            tree_preds = np.array([
                tree.predict(X_scaled)[0]
                for tree in model.estimators_
            ])
            pred_mean = float(np.mean(tree_preds))
            pred_std = float(np.std(tree_preds))

            predicted_visitors = max(0, round(pred_mean))
            lower = max(0, round(pred_mean - ci_multiplier * (pred_std + hist_std * 0.3)))
            upper = max(predicted_visitors, round(pred_mean + ci_multiplier * (pred_std + hist_std * 0.3)))

            day_name = HARI_INDONESIA.get(target_date.dayofweek, "")
            is_weekend = target_date.dayofweek in [5, 6]

            # Estimasi transaksi = visitor (1 transaksi ≈ 1 kunjungan, bisa disesuaikan)
            forecasts.append(DailyForecast(
                date=target_date.date(),
                predicted_visitors=predicted_visitors,
                predicted_transactions=predicted_visitors,
                lower_bound=lower,
                upper_bound=upper,
                day_of_week=day_name,
                is_weekend=is_weekend,
            ))

            # Update running history dengan prediksi terbaru
            new_row = pd.DataFrame([{
                "date": target_date,
                "visitors": float(predicted_visitors)
            }])
            running_history = pd.concat([running_history, new_row], ignore_index=True)

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

    # ─────────────────────────────────────────────────────────────
    # PERIODIC (WEEKLY / MONTHLY)
    # ─────────────────────────────────────────────────────────────

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
            raise ValueError(
                f"Tidak ada data historis untuk store {store_id}. "
                "Pastikan store sudah memiliki transaksi."
            )

        config = self._get_period_config(granularity)
        min_points = max(config["lags"]) + 1
        if len(df_period) < min_points:
            raise ValueError(
                f"Data historis terlalu sedikit: {len(df_period)} {granularity}. "
                f"Minimal dibutuhkan {min_points} periode."
            )

        df_features = self.preprocessor.engineer_features(
            df_period,
            lags=config["lags"],
            windows=config["windows"],
            expanding_min_periods=config["expanding_min_periods"],
        )
        feature_cols = self.preprocessor.get_feature_columns(df_features)

        meta = trainer.train(
            df_features,
            feature_cols,
            store_id,
            granularity=granularity,
        )
        return meta

    async def _forecast_periodic(
        self,
        store_id: str,
        forecast_periods: int,
        start_date: date | None,
        granularity: str,
    ):
        if not trainer.model_exists(store_id, granularity=granularity):
            logger.info(f"Model {granularity} belum ada untuk store {store_id}, auto-training...")
            await self._retrain_periodic(store_id, granularity)

        model, scaler, feature_cols, meta = trainer.load_model(
            store_id, granularity=granularity
        )

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
            row = self.preprocessor._build_future_row(
                target_date,
                running_history,
                lags=config["lags"],
                windows=config["windows"],
            )
            X_row = np.array([[row.get(col, 0.0) for col in feature_cols]])
            X_scaled = scaler.transform(X_row)

            tree_preds = np.array([
                tree.predict(X_scaled)[0]
                for tree in model.estimators_
            ])
            pred_mean = float(np.mean(tree_preds))
            pred_std = float(np.std(tree_preds))

            predicted_visitors = max(0, round(pred_mean))
            lower = max(0, round(pred_mean - ci_multiplier * (pred_std + hist_std * 0.3)))
            upper = max(predicted_visitors, round(pred_mean + ci_multiplier * (pred_std + hist_std * 0.3)))

            if granularity == "weekly":
                period_start = target_date.date()
                period_end = (target_date + timedelta(days=6)).date()
                week_of_year = int(target_date.isocalendar()[1])
                year = int(target_date.year)
                forecasts.append(WeeklyForecast(
                    period_start=period_start,
                    period_end=period_end,
                    predicted_visitors=predicted_visitors,
                    predicted_transactions=predicted_visitors,
                    lower_bound=lower,
                    upper_bound=upper,
                    week_of_year=week_of_year,
                    year=year,
                ))
            else:
                period_start = target_date.date()
                period_end = (target_date + pd.offsets.MonthEnd(0)).date()
                forecasts.append(MonthlyForecast(
                    period_start=period_start,
                    period_end=period_end,
                    predicted_visitors=predicted_visitors,
                    predicted_transactions=predicted_visitors,
                    lower_bound=lower,
                    upper_bound=upper,
                    month=int(target_date.month),
                    year=int(target_date.year),
                ))

            new_row = pd.DataFrame([{
                "date": target_date,
                "visitors": float(predicted_visitors)
            }])
            running_history = pd.concat([running_history, new_row], ignore_index=True)

        return forecasts, meta

    async def forecast_weekly(
        self,
        store_id: str,
        forecast_weeks: int,
        start_date: date | None,
    ) -> WeeklyForecastResponse:
        forecasts, meta = await self._forecast_periodic(
            store_id=store_id,
            forecast_periods=forecast_weeks,
            start_date=start_date,
            granularity="weekly",
        )
        return WeeklyForecastResponse(
            store_id=store_id,
            generated_at=datetime.utcnow(),
            forecast_horizon_weeks=forecast_weeks,
            forecasts=forecasts,
            model_metadata=ModelMetadata(
                trained_at=datetime.fromisoformat(meta["trained_at"]),
                training_data_points=meta["training_data_points"],
                feature_importance=meta.get("top_features", {}),
                cv_mae=meta["cv_mae"],
                cv_rmse=meta["cv_rmse"],
            ),
            status="success",
            message=f"Berhasil memprediksi {forecast_weeks} minggu ke depan",
        )

    async def forecast_monthly(
        self,
        store_id: str,
        forecast_months: int,
        start_date: date | None,
    ) -> MonthlyForecastResponse:
        forecasts, meta = await self._forecast_periodic(
            store_id=store_id,
            forecast_periods=forecast_months,
            start_date=start_date,
            granularity="monthly",
        )
        return MonthlyForecastResponse(
            store_id=store_id,
            generated_at=datetime.utcnow(),
            forecast_horizon_months=forecast_months,
            forecasts=forecasts,
            model_metadata=ModelMetadata(
                trained_at=datetime.fromisoformat(meta["trained_at"]),
                training_data_points=meta["training_data_points"],
                feature_importance=meta.get("top_features", {}),
                cv_mae=meta["cv_mae"],
                cv_rmse=meta["cv_rmse"],
            ),
            status="success",
            message=f"Berhasil memprediksi {forecast_months} bulan ke depan",
        )


# Singleton
forecast_service = ForecastService()
