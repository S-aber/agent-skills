import logging
import os
from logging.handlers import TimedRotatingFileHandler
from app.config import get_settings


def setup_logging():
    settings = get_settings()
    log_dir = settings.logs_dir
    os.makedirs(log_dir, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to avoid duplicates on reload
    root.handlers.clear()

    # Format
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler — daily rotation, keep 30 days
    app_log = os.path.join(log_dir, "app.log")
    file_handler = TimedRotatingFileHandler(
        app_log, when="midnight", interval=1, backupCount=30, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Error log — separate file for ERROR+ only
    error_log = os.path.join(log_dir, "error.log")
    err_handler = TimedRotatingFileHandler(
        error_log, when="midnight", interval=1, backupCount=30, encoding="utf-8"
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(fmt)
    root.addHandler(err_handler)

    # Suppress noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
