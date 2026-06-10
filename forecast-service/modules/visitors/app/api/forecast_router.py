"""
app/api/forecast_router.py
FastAPI router untuk semua endpoint forecasting.
"""
from fastapi import APIRouter, HTTPException, status
from datetime import date, datetime

from app.models.schemas import (
    ForecastRequest, ForecastResponse,
    ForecastWeeklyRequest, WeeklyForecastResponse,
    ForecastMonthlyRequest, MonthlyForecastResponse,
    RetrainRequest, RetrainResponse,
    ErrorResponse,
)
from app.services.forecast_service import forecast_service
from app.utils.logger import logger

router = APIRouter(prefix="/forecast", tags=["Forecast"])


@router.post(
    "/predict",
    response_model=ForecastResponse,
    summary="Prediksi jumlah pengunjung",
    description=(
        "Memprediksi jumlah pengunjung harian untuk N hari ke depan "
        "menggunakan model Random Forest yang sudah di-train. "
        "Jika model belum ada, service akan auto-train terlebih dahulu."
    ),
)
async def predict(request: ForecastRequest):
    """
    **Body:**
    - `store_id`: UUID store
    - `forecast_days`: jumlah hari prediksi (1–365, default 30)
    - `start_date`: tanggal mulai forecast (default: hari ini)

    **Response:** Daftar prediksi harian beserta confidence interval.
    """
    try:
        start = request.start_date or date.today()
        result = await forecast_service.forecast(
            store_id=request.store_id,
            forecast_days=request.forecast_days,
            start_date=start,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error saat predict: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/predict-weekly",
    response_model=WeeklyForecastResponse,
    summary="Prediksi jumlah pengunjung mingguan",
    description=(
        "Memprediksi jumlah pengunjung mingguan untuk N minggu ke depan "
        "menggunakan model Random Forest yang dilatih dari data DB."
    ),
)
async def predict_weekly(request: ForecastWeeklyRequest):
    """
    **Body:**
    - `store_id`: UUID store
    - `forecast_weeks`: jumlah minggu prediksi
    - `start_date`: tanggal mulai (akan disejajarkan ke awal minggu)
    """
    try:
        result = await forecast_service.forecast_weekly(
            store_id=request.store_id,
            forecast_weeks=request.forecast_weeks,
            start_date=request.start_date,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error saat predict-weekly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/predict-monthly",
    response_model=MonthlyForecastResponse,
    summary="Prediksi jumlah pengunjung bulanan",
    description=(
        "Memprediksi jumlah pengunjung bulanan untuk N bulan ke depan "
        "menggunakan model Random Forest yang dilatih dari data DB."
    ),
)
async def predict_monthly(request: ForecastMonthlyRequest):
    """
    **Body:**
    - `store_id`: UUID store
    - `forecast_months`: jumlah bulan prediksi
    - `start_date`: tanggal mulai (akan disejajarkan ke awal bulan)
    """
    try:
        result = await forecast_service.forecast_monthly(
            store_id=request.store_id,
            forecast_months=request.forecast_months,
            start_date=request.start_date,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error saat predict-monthly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/retrain",
    response_model=RetrainResponse,
    summary="Train ulang model untuk satu store",
    description=(
        "Mengambil data historis terbaru dari Golang API, "
        "melakukan feature engineering, dan melatih ulang model Random Forest."
    ),
)
async def retrain(request: RetrainRequest):
    """
    **Body:**
    - `store_id`: UUID store yang modelnya ingin di-retrain
    - `force`: paksa retrain meskipun model sudah up-to-date (default: false)
    """
    try:
        result = await forecast_service.retrain(
            store_id=request.store_id,
            force=request.force,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error saat retrain: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrain gagal: {str(e)}"
        )


@router.get(
    "/models",
    summary="Daftar model yang sudah di-train",
)
async def list_models():
    """
    Kembalikan semua store_id yang sudah memiliki model tersimpan di disk.
    """
    from app.training.trainer import trainer
    stores = trainer.list_trained_stores()
    return {
        "status": "success",
        "trained_store_count": len(stores),
        "store_ids": stores,
    }
