"""
Centralized logging setup for the Arma 3 Dedicated Launcher
-----------------------------------------------------------
Provides unified logging configuration for console + file outputs,
optional structured (JSON) logs, and rotation for large files.

Intended as logger for dockerized Arma 3 dedicated servers
"""

import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
_init_lock = threading.Lock()

def setup_logger(
    name: str = "arma_launcher",
    log_file: str = "/arma3/logs/launcher.log",
    level: str = "INFO",
    json_format: bool = False,
    max_size: int = 5_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """
    Initialize a logger with both console and rotating file output.

    Args:
        name: Logger name (default: "arma_launcher")
        log_file: Path to logfile (default: /arma3/logs/launcher.log)
        level: Log level string (DEBUG, INFO, WARNING, ERROR)
        json_format: Whether to output logs in JSON format (default: False)
        max_size: Max file size before rotation (bytes)
        backup_count: Number of rotated files to keep
    """
    logger = None
    with _init_lock:
        logger = logging.getLogger(name)
        if getattr(logger, "_arma_logger_initialized", False):
            return logger
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        logger.propagate = False  # prevent duplicate output

        # --- Formatter setup ---
        if json_format:
            formatter = JsonLogFormatter()
        else:
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

        # --- Console Handler ---
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # --- File Handler ---
        if log_file:
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                fh = RotatingFileHandler(str(log_path), maxBytes=max_size, backupCount=backup_count, encoding="utf-8")
                fh.setFormatter(formatter)
                logger.addHandler(fh)
            except OSError:
                # fallback: keep console logging and emit a warning to stderr
                warning = f"Could not open log file '{log_file}', continuing with console logging only."
                sys.stderr.write(warning + "\n")
                logger.warning(warning)
                
        logger._arma_logger_initialized = True
        logger.debug(f"Logger '{name}' initialized (level={level}, file={log_file})")
    return logger


class JsonLogFormatter(logging.Formatter):
    """
    Outputs log records as structured JSON.
    Useful for ingestion by ELK stacks or Docker logging systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        # Optional: include exception info if available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


# --- Helper to get logger globally ---
def get_logger(name: str = "arma_launcher") -> logging.Logger:
    """Retrieve the global launcher logger (if initialized)."""
    return logging.getLogger(name)
