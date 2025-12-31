from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict
from .models import RootConfig, MergedConfig
from .logging_setup import get_logger

log = get_logger("arma.launcher.config")

def load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config root must be an object")
    return data

def load_config(config_path: Path) -> MergedConfig:
    log.info("Loading config: %s", config_path)
    root = RootConfig.model_validate(load_json(config_path))
    merged = root.build_active()
    log.info("Active config: %s", merged.config_name)
    return merged
