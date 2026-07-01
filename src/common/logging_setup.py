import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

_CONFIGURED = False


def configure_logging(level: str = "INFO", to_file: bool = True, log_dir: str | Path = "outputs") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(console)
    if to_file:
        output_dir = Path(log_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            output_dir / "floodai.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)
    _CONFIGURED = True


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    if not _CONFIGURED:
        configure_logging(level=level)
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger
