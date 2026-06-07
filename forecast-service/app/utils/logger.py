"""
app/utils/logger.py
Centralized logging configuration.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from app.utils.config import settings


def setup_logger(name: str = "forecast_service") -> logging.Logger:
    """
    Setup logger with file and console handlers.
    """
    os.makedirs(settings.log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Avoid duplicate handlers on reload
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler (10 MB per file, keep 5 backups)
    log_file = os.path.join(settings.log_dir, "forecast_service.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
