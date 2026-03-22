import logging
import os
from logging.handlers import RotatingFileHandler

_LOGGERS = {}


def get_logger(app_dir: str, name: str = "elvar"):
    key = (app_dir, name)
    if key in _LOGGERS:
        return _LOGGERS[key]

    os.makedirs(app_dir, exist_ok=True)
    log_path = os.path.join(app_dir, "elvar.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    _LOGGERS[key] = logger
    return logger
