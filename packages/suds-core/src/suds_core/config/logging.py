# packages/suds-core/src/suds_core/config/logging.py
from __future__ import annotations

import logging
import sys
from typing import Optional


def configure_logging(level: str = "INFO", logger_name: Optional[str] = None) -> logging.Logger:
    """
    Minimal structured logging-ish config.

    In production you might replace this with:
    - structlog
    - or JSON logging via python-json-logger
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
    )

    return logging.getLogger(logger_name or "suds")