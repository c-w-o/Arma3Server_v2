"""_summary_

Returns:
    _type_: _description_
    
Part of Arma 3 dedicated server launcher for dockerized server instances.
"""
import os
import json
from pathlib import Path
from typing import Optional, Dict
from arma_launcher.log import get_logger, setup_logger
logger = get_logger()


def _load_steam_credentials():
    cfg_path = os.environ.get("ARMA_CONFIG_JSON", "/var/run/share/steam_credentials.json")
    if os.path.isfile(cfg_path):
        try:
            logger.debug(f"opening {cfg_path} as credential file")
            with open(cfg_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                logger.info("loaded steam credentials from file")
            return data.get("steam_user"), data.get("steam_password")
        except Exception:
            pass
    # fallback: environment variables (optional)
    logger.warning(f"stream credentials {cfg_path} file not found, try loading from environment")
    return os.environ.get("STEAM_USER"), os.environ.get("STEAM_PASSWORD")

def _safe_int(value, default, name=None):
    try:
        return int(value)
    except Exception:
        if name:
            logger.warning(f"Invalid integer for {name}: {value!r}, using {default}")
        return default
    
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
        self.tmp_dir = Path(data.get("TMP_DIR", "/tmp"))

        self.basic_config = data.get("BASIC_CONFIG", "basic.cfg")
        self.arma_config = data.get("ARMA_CONFIG", "generated_a3server.cfg")
        self.param_config = data.get("PARAM_CONFIG", "params.cfg")
        self.mods_preset = data.get("MODS_PRESET", "mods.json")

        self.steam_user = data.get("STEAM_USER", "")
        self.steam_password = data.get("STEAM_PASSWORD", "")
        self.skip_install = data.get("SKIP_INSTALL", "false").lower() == "true"
        
        self.common_share = Path("/var/run/share/arma3/server-common")
        self.this_share = Path("/var/run/share/arma3/this-server")
        
        self.this_server_mods = self.this_share / "servermods"
        self.this_mission_mods = self.this_share / "mods"
        self.common_server_mods = self.common_share / "mods"
        self.common_base_mods = self.common_share / "mods"
        self.common_maps = self.common_share / "mods"

        # fallback: load credentials from credentials file or alternate env vars
        if not self.steam_user or not self.steam_password:
            file_user, file_pass = _load_steam_credentials()
            if file_user:
                self.steam_user = file_user
            if file_pass:
                self.steam_password = file_pass
            if self.steam_user or self.steam_password:
                logger.info("Steam credentials loaded from file")
        self.limit_fps = _safe_int(data.get("ARMA_LIMITFPS", "120"), 120, "ARMA_LIMITFPS")
        self.world = data.get("ARMA_WORLD", "empty")
        self.port = _safe_int(int(data.get("PORT", 2302)), 2302, "PORT")
        self.profile = data.get("ARMA_PROFILE", "server")
        self.headless_clients = _safe_int(int(data.get("HEADLESS_CLIENTS", 0)), 0, "HEADLESS_CLIENTS")
        self.use_ocap = False
        self.mods = []
        self.servermods = []
        self.maps = []
        self.clientmods = []
        # list of DLC/app IDs to ensure installed (from JSON defaults/active)
        self.dlcs = []
        # JSON-based override (server.json)
        self.json_file = self.this_share / "config/server.json"
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

    @classmethod
    def from_env(cls, env: dict = None):
        """
        Construct ArmaConfig from an environment mapping (defaults to os.environ).
        This replaces the missing from_env used by launcher.py.
        """
        if env is None:
            env = os.environ
        keys = [
            "ARMA_ROOT", "TMP_DIR", "BASIC_CONFIG", "ARMA_CONFIG", "PARAM_CONFIG",
            "MODS_PRESET", "STEAM_USER", "STEAM_PASSWORD", "SKIP_INSTALL",
            "ARMA_LIMITFPS", "ARMA_WORLD", "PORT", "ARMA_PROFILE", "HEADLESS_CLIENTS",
        ]
        data = {k: env.get(k) for k in keys}
        # Also include any other env vars the constructor checks directly
        # (keeps future compatibility)
        data.update({k: env.get(k) for k in env.keys() if k not in data})
        return cls(data)

    def get_merged_config(self) -> dict:
        """
        Return a merged configuration dict: defaults overridden by active config.
        - top-level values: active overrides defaults
        - 'mods': merge keys, concatenate lists (defaults then active)
        - 'params', 'missions': concatenate defaults then active
        - 'dlcs': prefer active if present, else defaults
        """
        if getattr(self, "_merged_config_cached", None) is not None:
            return self._merged_config_cached

        json_data = getattr(self, "json_data", None) or {}
        if not json_data:
            self._merged_config_cached = {}
            return self._merged_config_cached

        defaults = json_data.get("defaults", {}) or {}
        active_name = json_data.get("config-name")
        active = (json_data.get("configs", {}) or {}).get(active_name, {}) or {}

        merged = {}
        # shallow merge: active overrides defaults
        merged.update(defaults)
        merged.update(active)

        # mods: merge dict keys, concat lists (defaults first)
        defaults_mods = defaults.get("mods", {}) or {}
        active_mods = active.get("mods", {}) or {}
        merged_mods = {}
        for k in set(defaults_mods.keys()) | set(active_mods.keys()):
            dlist = defaults_mods.get(k, []) or []
            alist = active_mods.get(k, []) or []
            merged_mods[k] = list(dlist) + list(alist)
        merged["mods"] = merged_mods

        # params, missions: concat lists (defaults then active)
        merged["params"] = list(defaults.get("params", []) or []) + list(active.get("params", []) or [])
        merged["missions"] = list(defaults.get("missions", []) or []) + list(active.get("missions", []) or [])

        # dlcs: prefer active value if present, else defaults
        if "dlcs" in active:
            merged["dlcs"] = active.get("dlcs")
        else:
            merged["dlcs"] = defaults.get("dlcs", {})

        self._merged_config_cached = merged
        return merged

    def _apply_json_overrides(self):
        """Apply JSON config to object attributes and expose merged view."""
        # ...existing code that loads self.json_data ...
        # ensure merged view is available for other modules
        merged = self.get_merged_config()
        self.json_merged = merged
        # convenience attributes
        self.mods = merged.get("mods", {})
        self.params = merged.get("params", [])
        self.missions = merged.get("missions", [])
        self.dlcs = merged.get("dlcs", {})

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