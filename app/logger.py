import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "/home/vinay/kiosk-logs"
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(name, filename):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=5_000_000,   # 5MB
        backupCount=5
    )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger

app_logger = setup_logger("APP", "app.log")
health_logger = setup_logger("HEALTH", "health.log")
event_logger = setup_logger("EVENT", "events.log")
