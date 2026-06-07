"""
main.py
Entry point Sora Forecast Service.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

from app.api.forecast_router import router as forecast_router
from app.api.health_router import router as health_router
from app.utils.config import settings
from app.utils.logger import logger


# ─── Scheduler untuk auto-retrain berkala ─────────────────────────────────────
scheduler = AsyncIOScheduler()


async def scheduled_retrain_all():
    """
    Retrain semua model yang ada secara berkala (sesuai RETRAIN_INTERVAL_DAYS).
    """
    from app.training.trainer import trainer
    from app.services.forecast_service import forecast_service

    store_ids = trainer.list_trained_stores()
    if not store_ids:
        logger.info("[Scheduler] Tidak ada model untuk di-retrain")
        return

    logger.info(f"[Scheduler] Memulai retrain untuk {len(store_ids)} store...")
    for store_id in store_ids:
        try:
            await forecast_service.retrain(store_id=store_id, force=True)
            logger.info(f"[Scheduler] Retrain selesai: {store_id}")
        except Exception as e:
            logger.error(f"[Scheduler] Retrain gagal untuk {store_id}: {e}")


# ─── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: mulai scheduler.
    Shutdown: hentikan scheduler.
    """
    logger.info("=" * 60)
    logger.info("  Sora Forecast Service - Starting Up")
    logger.info(f"  Golang API : {settings.golang_api_base_url}")
    logger.info(f"  Model Dir  : {settings.model_dir}")
    logger.info(f"  Environment: {settings.service_env}")
    logger.info("=" * 60)

    os.makedirs(settings.model_dir, exist_ok=True)

    # Jadwalkan retrain setiap N hari
    scheduler.add_job(
        scheduled_retrain_all,
        trigger="interval",
        days=settings.retrain_interval_days,
        id="auto_retrain",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler aktif: retrain setiap {settings.retrain_interval_days} hari")

    yield  # ← aplikasi berjalan di sini

    scheduler.shutdown()
    logger.info("Sora Forecast Service - Shutdown selesai")


# ─── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sora Forecast Service",
    description=(
        "Microservice untuk forecasting jumlah pengunjung restoran "
        "menggunakan Random Forest. Terintegrasi dengan Golang API Sora Finance."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS (sesuaikan allowed_origins untuk production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router
app.include_router(health_router)
app.include_router(forecast_router, prefix="/api")


# ─── Jalankan dengan Uvicorn ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=(settings.service_env == "development"),
        log_level=settings.log_level.lower(),
    )
