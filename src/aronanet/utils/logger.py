# Same logger as Project-Ibuki lol
import logging
from pathlib import Path

def get_logger(name: str = "app_logger") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logger.setLevel(logging.DEBUG)

        log_dir = Path.home() / ".aronanet" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = str(log_dir / "AronaNET.log")

        fh = logging.FileHandler(log_path, mode="a")
        fh.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(formatter)

        logger.addHandler(fh)
    return logger
