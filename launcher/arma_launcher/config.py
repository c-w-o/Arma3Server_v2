"""_summary_

Returns:
    _type_: _description_
    
Part of Arma 3 dedicated server launcher for dockerized server instances.
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict
from arma_launcher.log import get_logger, setup_logger
logger = get_logger()


def _load_steam_credentials():
    cfg_path = os.environ.get("ARMA_CONFIG_JSON", "/var/run/share/steam_credentials.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                logger.info("loaded steam credentials from file")
            return data.get("steam_user"), data.get("steam_password")
        except Exception:
            pass
    # fallback: environment variables (optional)
    logger.warning("stream credentials file not found, try loading from environment")
    return os.environ.get("STEAM_USER"), os.environ.get("STEAM_PASSWORD")


class ArmaConfig:
    """
    Central configuration for the Arma 3 dedicated launcher.
    Loads values from environment and optional JSON file (server.json).
    """

    def __init__(self, data: Dict[str, str]):
        self.arma_root = Path(data.get("ARMA_ROOT", "/arma3"))
        self.config_dir = self.arma_root / "config"
        self.mods_dir = self.arma_root / "mods"
        self.servermods_dir = self.arma_root / "servermods"
        self.keys_dir = self.arma_root / "keys"
        self.tmp_dir = Path(data.get("TMP_DIR", "/tmp/steamapps/workshop/content/107410"))

        self.basic_config = data.get("BASIC_CONFIG", "basic.cfg")
        self.arma_config = data.get("ARMA_CONFIG", "server.cfg")
        self.param_config = data.get("PARAM_CONFIG", "params.cfg")
        self.mods_preset = data.get("MODS_PRESET", "mods.json")

        self.steam_user = data.get("STEAM_USER", "")
        self.steam_password = data.get("STEAM_PASSWORD", "")
        self.skip_install = data.get("SKIP_INSTALL", "false").lower() == "true"

        # fallback: load credentials from credentials file or alternate env vars
        if not self.steam_user or not self.steam_password:
            file_user, file_pass = _load_steam_credentials()
            if file_user:
                self.steam_user = file_user
            if file_pass:
                self.steam_password = file_pass
            if self.steam_user or self.steam_password:
                logger.info("Steam credentials loaded from fallback")
        
        def _safe_int(value, default, name=None):
            try:
                return int(value)
            except Exception:
                if name:
                    logger.warning(f"Invalid integer for {name}: {value!r}, using {default}")
                return default

        self.limit_fps = _safe_int(data.get("ARMA_LIMITFPS", "120"), 120, "ARMA_LIMITFPS")
        self.world = data.get("ARMA_WORLD", "empty")
        self.port = _safe_int(int(data.get("PORT", 2302)), 2302, "PORT")
        self.profile = data.get("ARMA_PROFILE", "default")
        self.headless_clients = _safe_int(int(data.get("HEADLESS_CLIENTS", 0)), 0, "HEADLESS_CLIENTS")
        self.use_ocap = False
        
        self.mods = []
        self.servermods = []
        self.maps = []
        self.clientmods = []
        
        # JSON-based override (server.json)
        self.json_file = self.config_dir / "server.json"
        self.json_data = {}
        if self.json_file.exists():
            try:
                with open(self.json_file, "r", encoding="utf-8") as f:
                    self.json_data = json.load(f)
                logger.info(f"Loaded JSON configuration: {self.json_file}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in {self.json_file}: {e}")
            except OSError as e:
                logger.error(f"I/O error reading {self.json_file}: {e}")
            except Exception:
                logger.exception(f"Unexpected error loading {self.json_file}")

        # Apply JSON overrides if available
        self._apply_json_overrides()

    def _apply_json_overrides(self):
        if not self.json_data:
            return
        active_name = self.json_data.get("config-name")
        if not active_name:
            return
        active_cfg = self.json_data.get("configs", {}).get(active_name, {})
        if not active_cfg:
            logger.warning(f"No matching config '{active_name}' found in server.json")
            return

        self.use_ocap = active_cfg.get("use-ocap", False)
        self.mods = active_cfg.get("mods", [])
        self.servermods = active_cfg.get("servermods", [])
        self.maps = active_cfg.get("maps", [])
        self.clientmods = active_cfg.get("client-side-mods", [])

        logger.info(f"Loaded profile '{active_name}' from JSON (OCAP={self.use_ocap})")

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables."""
        data = dict(os.environ)
        return cls(data)


# --- Logging setup ---
def setup_logging(log_file: Optional[str] = "/arma3/logs/launcher.log"):
    # Delegate logging setup to central logger in arma_launcher.log
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    # try to use JSON logging if requested via ENV
    json_fmt = os.getenv("LOG_JSON", "false").lower() == "true"
    setup_logger(name="arma_launcher", log_file=log_file, level=level, json_format=json_fmt)

# set module-level defaults if not already set by existing code
try:
    steam_user  # if already defined earlier in file, keep it
except NameError:
    steam_user, steam_password = _load_steam_credentials()