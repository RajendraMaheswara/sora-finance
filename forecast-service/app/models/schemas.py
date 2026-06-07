"""
app/models/schemas.py
Pydantic schemas for API request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


# ─────────────────────────────────────────────
# Request Schemas
# ─────────────────────────────────────────────

class ForecastRequest(BaseModel):
    store_id: str = Field(..., description="UUID store yang ingin di-forecast")
    forecast_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Jumlah hari ke depan yang ingin diprediksi (1–365)"
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Tanggal mulai forecast. Default: hari ini"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "store_id": "550e8400-e29b-41d4-a716-446655440000",
            "forecast_days": 30,
            "start_date": "2025-01-01"
        }
    }}


class ForecastWeeklyRequest(BaseModel):
    store_id: str = Field(..., description="UUID store yang ingin di-forecast")
    forecast_weeks: int = Field(
        default=8,
        ge=1,
        le=260,
        description="Jumlah minggu ke depan yang ingin diprediksi (1–260)"
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Tanggal mulai forecast (akan disejajarkan ke awal minggu)"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "store_id": "550e8400-e29b-41d4-a716-446655440000",
            "forecast_weeks": 8,
            "start_date": "2025-01-06"
        }
    }}


class ForecastMonthlyRequest(BaseModel):
    store_id: str = Field(..., description="UUID store yang ingin di-forecast")
    forecast_months: int = Field(
        default=6,
        ge=1,
        le=120,
        description="Jumlah bulan ke depan yang ingin diprediksi (1–120)"
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Tanggal mulai forecast (akan disejajarkan ke awal bulan)"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "store_id": "550e8400-e29b-41d4-a716-446655440000",
            "forecast_months": 6,
            "start_date": "2025-02-01"
        }
    }}


class RetrainRequest(BaseModel):
    store_id: str = Field(..., description="UUID store yang modelnya ingin di-retrain")
    force: bool = Field(
        default=False,
        description="Paksa retrain meskipun model sudah baru"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "store_id": "550e8400-e29b-41d4-a716-446655440000",
            "force": True
        }
    }}


# ─────────────────────────────────────────────
# Response Schemas
# ─────────────────────────────────────────────

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


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    golang_api_reachable: bool
    loaded_models: List[str]
    timestamp: datetime


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: Optional[str] = None
