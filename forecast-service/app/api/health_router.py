"""
app/api/health_router.py
Endpoint health check untuk monitoring & readiness probe.
"""
from fastapi import APIRouter
from datetime import datetime

from app.models.schemas import HealthResponse
from app.services.golang_client import golang_client
from app.training.trainer import trainer

router = APIRouter(tags=["Health"])

SERVICE_VERSION = "1.0.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Cek status service, konektivitas ke Golang API, dan model yang sudah di-load.",
)
async def health_check():
    golang_reachable = await golang_client.is_reachable()
    loaded_models = trainer.list_trained_stores()

    return HealthResponse(
        status="healthy" if golang_reachable else "degraded",
        service="sora-forecast-service",
        version=SERVICE_VERSION,
        golang_api_reachable=golang_reachable,
        loaded_models=loaded_models,
        timestamp=datetime.utcnow(),
    )


@router.get("/", include_in_schema=False)
async def root():
    return {
        "service": "Sora Forecast Service",
        "version": SERVICE_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
