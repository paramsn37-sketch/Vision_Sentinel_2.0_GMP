"""Structured JSON logs (structlog) to stderr and a rotating file under the data directory."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

import structlog


def setup_logging(data_dir: Path, level: int = logging.INFO) -> None:
    if getattr(setup_logging, "_done", False):
        return
    setup_logging._done = True  # type: ignore[attr-defined]
    data_dir.mkdir(parents=True, exist_ok=True)
    shared = [structlog.stdlib.add_log_level, structlog.processors.TimeStamper(fmt="iso", utc=True)]
    formatter = structlog.stdlib.ProcessorFormatter(processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                                                                structlog.processors.JSONRenderer()], foreign_pre_chain=shared)  # fmt: skip
    file = logging.handlers.RotatingFileHandler(
        data_dir / "vision_sentinel.log", maxBytes=10_000_000, backupCount=5
    )
    file.setFormatter(formatter)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [stream, file]
    root.setLevel(level)
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    structlog.configure(processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
                        logger_factory=structlog.stdlib.LoggerFactory())  # fmt: skip
