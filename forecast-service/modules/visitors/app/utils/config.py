"""
app/utils/config.py
Centralized configuration using pydantic-settings.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_ENV = BASE_DIR.parent / "backend" / ".env"
ENV_FILES = [".env"]
if BACKEND_ENV.exists():
    ENV_FILES.append(str(BACKEND_ENV))


class Settings(BaseSettings):
    # Golang API
    golang_api_base_url: str = Field(
        default="http://localhost:8080/api",
        env="GOLANG_API_BASE_URL"
    )

    # Database (Postgres)
    db_host: str = Field(default="", env="DB_HOST")
    db_port: str = Field(default="", env="DB_PORT")
    db_user: str = Field(default="", env="DB_USER")
    db_password: str = Field(default="", env="DB_PASSWORD")
    db_name: str = Field(default="", env="DB_NAME")
    db_sslmode: str = Field(default="disable", env="DB_SSLMODE")

    # Service Config
    service_host: str = Field(default="0.0.0.0", env="SERVICE_HOST")
    service_port: int = Field(default=5000, env="SERVICE_PORT")
    service_env: str = Field(default="development", env="SERVICE_ENV")

    # Model Config
    model_dir: str = Field(default="../../models/visitors", env="MODEL_DIR")
    forecast_horizon_days: int = Field(default=30, env="FORECAST_HORIZON_DAYS")
    retrain_interval_days: int = Field(default=7, env="RETRAIN_INTERVAL_DAYS")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_dir: str = Field(default="logs", env="LOG_DIR")

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )


# Singleton instance
settings = Settings()
