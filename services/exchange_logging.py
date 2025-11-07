import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import os
LOG_PATH = Path(os.getenv("EXCHANGE_LOG_PATH", "logs/exchange_traffic.log"))


def get_exchange_logger() -> logging.Logger:
    logger = logging.getLogger("exchange")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def jlog(logger: logging.Logger, payload: dict) -> None:
    try:
        logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.info(str(payload))


