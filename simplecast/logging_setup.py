from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SimpleCast"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "simplecast.log"
    handler = RotatingFileHandler(
        path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    return path
