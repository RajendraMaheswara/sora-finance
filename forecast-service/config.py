import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8080/api')
    
    # Inventory Configs
    MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
    TRAINING_MAX_WORKERS = int(os.getenv('TRAINING_MAX_WORKERS', 4))
    
    # Sales Configs
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SALES_MODELS_DIR = os.path.join(MODEL_DIR, "sales")

    # Visitors Configs
    GOLANG_API_BASE_URL = os.getenv('GOLANG_API_BASE_URL', 'http://localhost:8080/api')
    VISITORS_MODEL_DIR = os.getenv('MODEL_DIR', os.path.join(MODEL_DIR, "visitors"))
    VISITORS_FORECAST_HORIZON_DAYS = int(os.getenv('FORECAST_HORIZON_DAYS', 30))
    VISITORS_RETRAIN_INTERVAL_DAYS = int(os.getenv('RETRAIN_INTERVAL_DAYS', 7))
    
    DAILY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_daily.joblib")
    WEEKLY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_weekly.joblib")
    MONTHLY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_monthly.joblib")

    @staticmethod
    def init_app():
        os.makedirs(Config.SALES_MODELS_DIR, exist_ok=True)
        os.makedirs(os.path.join(Config.MODEL_DIR, 'inventory'), exist_ok=True)
        os.makedirs(Config.VISITORS_MODEL_DIR, exist_ok=True)