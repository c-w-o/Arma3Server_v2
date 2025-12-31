from __future__ import annotations
import json
from pathlib import Path
from typing import Tuple
from .settings import Settings
from .logging_setup import get_logger

log = get_logger("arma.launcher.steam")

def load_credentials(settings: Settings) -> Tuple[str, str]:
    if settings.steam_user and settings.steam_password:
        return settings.steam_user, settings.steam_password

    p = settings.steam_credentials_json
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            user = str(data.get("steam_user", "")).strip()
            pw = str(data.get("steam_password", "")).strip()
            if user and pw:
                return user, pw
        except Exception as e:
            log.warning("Failed to read %s: %s", p, e)

    raise RuntimeError("Steam credentials missing. Provide STEAM_USER/STEAM_PASSWORD or steam_credentials.json")
