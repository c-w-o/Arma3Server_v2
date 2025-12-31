from __future__ import annotations
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .settings import Settings

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def setup_logging(settings: Settings) -> None:
    logs_dir = settings.arma_instance / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.log_level.upper())

    fmt = _JsonFormatter() if settings.log_json else logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    launcher_fh = RotatingFileHandler(logs_dir / "launcher.log", maxBytes=5_000_000, backupCount=3)
    launcher_fh.setFormatter(fmt)
    launcher_fh.setLevel(settings.log_level.upper())
    logging.getLogger("arma.launcher").addHandler(launcher_fh)
    logging.getLogger("arma.launcher").propagate = True

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
