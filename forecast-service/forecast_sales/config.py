import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8080/api")
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MODELS_DIR = os.path.join(BASE_DIR, "models")
    SALES_MODELS_DIR = os.path.join(MODELS_DIR, "sales")
    
    DAILY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_daily.joblib")
    WEEKLY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_weekly.joblib") # TAMBAHAN BARU
    MONTHLY_MODEL_PATH = os.path.join(SALES_MODELS_DIR, "models_rf_monthly.joblib")

    @staticmethod
    def init_app():
        os.makedirs(Config.SALES_MODELS_DIR, exist_ok=True)