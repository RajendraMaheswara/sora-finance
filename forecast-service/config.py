import os
from dotenv import load_dotenv

load_dotenv()

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default

class Config:
    BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8080/api')
    INTERNAL_SERVICE_KEY = os.getenv('INTERNAL_SERVICE_KEY', '')
    BACKEND_REQUEST_TIMEOUT_SECONDS = float(os.getenv('BACKEND_REQUEST_TIMEOUT_SECONDS', '30'))

    # Forecast runtime / scheduler. Satu mode saja:
    # - manual: scheduler mati, endpoint manual tetap aktif
    # - scheduler: visitors scheduler aktif dan mengecek operational hours store
    FORECAST_MODE = os.getenv('FORECAST_MODE', 'manual').strip().lower()
    FORECAST_SCHEDULER_TIMEZONE = os.getenv('FORECAST_SCHEDULER_TIMEZONE', 'Asia/Jakarta')
    FORECAST_AFTER_CLOSE_SCHEDULER_MINUTES = _env_int('FORECAST_AFTER_CLOSE_SCHEDULER_MINUTES', 60)
    FORECAST_24H_RUN_SCHEDULER_MINUTES = _env_int('FORECAST_24H_RUN_SCHEDULER_MINUTES', 120)
    FORECAST_SCHEDULER_CHECK_INTERVAL_MINUTES = max(1, _env_int('FORECAST_SCHEDULER_CHECK_INTERVAL_MINUTES', 15))
    SCHEDULER_RETRAIN = _env_bool('SCHEDULER_RETRAIN', True)
    
    # Inventory Configs
    MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
    TRAINING_MAX_WORKERS = int(os.getenv('TRAINING_MAX_WORKERS', 4))
    
    # Sales Configs
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SALES_MODELS_DIR = os.path.join(MODEL_DIR, "sales")

    # Visitors Configs
    # Default diarahkan ke backend internal forecast routes. Route ini dilindungi
    # INTERNAL_SERVICE_KEY melalui header X-Service-Key.
    GOLANG_API_BASE_URL = os.getenv('GOLANG_API_BASE_URL', 'http://localhost:8080/internal/forecast')
    GOLANG_INTERNAL_API_BASE_URL = os.getenv('GOLANG_INTERNAL_API_BASE_URL', GOLANG_API_BASE_URL)
    VISITORS_MODEL_DIR = os.getenv('MODEL_DIR', os.path.join(MODEL_DIR, "visitors"))
    VISITORS_FORECAST_HORIZON_DAYS = int(os.getenv('FORECAST_HORIZON_DAYS', 30))
    VISITORS_RETRAIN_INTERVAL_DAYS = int(os.getenv('RETRAIN_INTERVAL_DAYS', 7))
    
    DAILY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_daily.joblib")
    WEEKLY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_weekly.joblib")
    MONTHLY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_monthly.joblib")


    @staticmethod
    def backend_headers():
        headers = {}
        if Config.INTERNAL_SERVICE_KEY:
            headers['X-Service-Key'] = Config.INTERNAL_SERVICE_KEY
        return headers

    @staticmethod
    def init_app():
        os.makedirs(Config.SALES_MODELS_DIR, exist_ok=True)
        os.makedirs(os.path.join(Config.MODEL_DIR, 'inventory'), exist_ok=True)
        os.makedirs(Config.VISITORS_MODEL_DIR, exist_ok=True)