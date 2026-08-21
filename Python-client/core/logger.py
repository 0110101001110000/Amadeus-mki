"""
Global logging configuration.
"""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


# Global -------------------------------------------------------------------- #


LOG_DIR: Path = Path("logs")
LOG_FILE: Path = LOG_DIR / "application.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)


# Functions ----------------------------------------------------------------- #


def setup_logging(level: str = "INFO") -> None:
    """
    Configure global application logging.
    """
    logger: logging.Logger = logging.getLogger()

    if logger.handlers:
        return

    logger.setLevel(
        getattr(logging, level.upper(), logging.INFO)
    )

    formatter = logging.Formatter(
        fmt=(
            "[%(asctime)s] "
            "[%(levelname)s] "
            "[%(name)s] "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.propagate = False
