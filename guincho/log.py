import logging
from datetime import datetime

from . import config


def obter_logger() -> logging.Logger:
    logger = logging.getLogger("guincho")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    arquivo = config.PASTA_LOGS / f"guincho_{datetime.now():%Y-%m}.log"
    fh = logging.FileHandler(arquivo, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
