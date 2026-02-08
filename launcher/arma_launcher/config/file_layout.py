"""
Verzeichnis-Layout für Multi-File Config-Struktur.

Verwaltet die physische Ablage:
    instance/config/
    ├── server.json
    ├── defaults/
    │   ├── mods.json
    │   ├── dlcs.json
    │   └── server.json
    └── configs/
        ├── production/
        │   ├── metadata.json
        │   ├── mods.json
        │   ├── dlcs.json
        │   └── server.json
        └── event/
            └── ...
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from ..logging_setup import get_logger

log = get_logger("arma.config.layout")


class ConfigLayout:
    """Zentrale Verwaltung der Config-Verzeichnisstruktur."""
    
    def __init__(self, root_config_dir: Path):
        """
        Args:
            root_config_dir: Absoluter Pfad zu instance/config/
        """
        self.root = Path(root_config_dir)
        if not self.root.is_absolute():
            raise ValueError(f"root_config_dir must be absolute, got {self.root}")
    
    # === Master Index ===
    @property
    def server_json(self) -> Path:
        """Master server.json mit Metadaten und activeConfig."""
        return self.root / "server.json"
    
    # === Defaults ===
    @property
    def defaults_dir(self) -> Path:
        """Verzeichnis für Basis-Einstellungen."""
        return self.root / "defaults"
    
    def defaults_mods_json(self) -> Path:
        """defaults/mods.json - Standard Mod-Konfiguration."""
        return self.defaults_dir / "mods.json"
    
    def defaults_dlcs_json(self) -> Path:
        """defaults/dlcs.json - Standard DLC-Flags."""
        return self.defaults_dir / "dlcs.json"
    
    def defaults_server_json(self) -> Path:
        """defaults/server.json - Server-Einstellungen (hostname, port, etc.)."""
        return self.defaults_dir / "server.json"
    
    def defaults_missions_json(self) -> Path:
        """defaults/missions.json - Standard-Missionen."""
        return self.defaults_dir / "missions.json"
    
    # === Configs ===
    @property
    def configs_dir(self) -> Path:
        """Verzeichnis für alle Konfigurationen."""
        return self.root / "configs"
    
    def config_dir(self, name: str) -> Path:
        """Verzeichnis für eine spezifische Konfiguration."""
        return self.configs_dir / name
    
    def config_metadata_json(self, name: str) -> Path:
        """configs/{name}/metadata.json - Metadaten (erstellt, modifiziert, beschreibung)."""
        return self.config_dir(name) / "metadata.json"
    
    def config_mods_json(self, name: str) -> Path:
        """configs/{name}/mods.json - Mod-Overrides."""
        return self.config_dir(name) / "mods.json"
    
    def config_dlcs_json(self, name: str) -> Path:
        """configs/{name}/dlcs.json - DLC-Overrides."""
        return self.config_dir(name) / "dlcs.json"
    
    def config_server_json(self, name: str) -> Path:
        """configs/{name}/server.json - Server-Setting Overrides."""
        return self.config_dir(name) / "server.json"
    
    # === Variants (NEW: Basis + Varianten) ===
    @property
    def variants_dir(self) -> Path:
        """Verzeichnis für alle Varianten."""
        return self.root / "variants"
    
    def variant_dir(self, name: str) -> Path:
        """Verzeichnis für eine spezifische Variante."""
        return self.variants_dir / name
    
    def variant_mods_json(self, name: str) -> Path:
        """variants/{name}/mods.json - Mod-Overrides für Variante."""
        return self.variant_dir(name) / "mods.json"
    
    def variant_metadata_json(self, name: str) -> Path:
        """variants/{name}/metadata.json - Metadaten (erstellt, modifiziert, description)."""
        return self.variant_dir(name) / "metadata.json"
    
    def variant_settings_json(self, name: str) -> Path:
        """variants/{name}/settings.json - Server-Einstellungen Overrides (optional)."""
        return self.variant_dir(name) / "settings.json"
    
    # === Server Settings (NEW: Global) ===
    @property
    def server_settings_json(self) -> Path:
        """server-settings.json - Globale Server-Einstellungen."""
        return self.root / "server-settings.json"
    
    # === Cache ===
    @property
    def cache_dir(self) -> Path:
        """Verzeichnis für Caches (Steam-Metadaten, etc.)."""
        return self.root / "cache"
    
    @property
    def workshop_metadata_json(self) -> Path:
        """cache/workshop_metadata.json - Gecachte Workshop-Items."""
        return self.cache_dir / "workshop_metadata.json"
    
    @property
    def steam_aliases_json(self) -> Path:
        """cache/steam_aliases.json - Mod ID → Name Mapping."""
        return self.cache_dir / "steam_aliases.json"
    
    # === Backups (optional) ===
    @property
    def backups_dir(self) -> Path:
        """Verzeichnis für Backup-Snapshots."""
        return self.root / "backups"
    
    def backup_dir(self, timestamp: str) -> Path:
        """backups/{timestamp}/ - Ein Backup-Snapshot."""
        return self.backups_dir / timestamp
    
    # === Directory Management ===
    def ensure_structure(self) -> None:
        """Erstellt alle notwendigen Verzeichnisse und initialisiert server.json wenn nötig."""
        dirs = [
            self.defaults_dir,
            self.configs_dir,
            self.variants_dir,
            self.cache_dir,
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            log.debug(f"Ensured directory: {d}")
        
        # Initialisiere server.json wenn nicht vorhanden
        if not self.server_json.exists():
            self._init_server_json()
        
        # Initialisiere defaults/*.json wenn nicht vorhanden
        self._init_defaults()
    
    def _init_server_json(self) -> None:
        """Erstellt initial server.json."""
        import json
        from datetime import datetime, timezone
        
        initial_data = {
            "version": "2",
            "created": datetime.now(timezone.utc).isoformat(),
            "lastModified": datetime.now(timezone.utc).isoformat(),
            "activeConfig": "production",
            "configs": [],
            "metadata": {
                "schemaVersion": "2.0",
                "description": "Arma3 Launcher v2 Multi-File Configuration"
            }
        }
        
        self.server_json.write_text(json.dumps(initial_data, indent=2))
        log.info(f"Initialized: {self.server_json}")
    
    def _init_defaults(self) -> None:
        """Erstellt leere defaults/*.json wenn nicht vorhanden."""
        import json
        
        defaults_template = {
            "mods": {
                "serverMods": [],
                "baseMods": [],
                "clientMods": [],
                "maps": [],
                "missionMods": [],
                "extraServer": [],
                "extraBase": [],
                "extraClient": [],
                "extraMaps": [],
                "extraMission": [],
                "minus_mods": []
            },
            "dlcs": {
                "contact": False,
                "csla_iron_curtain": False,
                "global_mobilization": False,
                "s.o.g_prairie_fire": False,
                "western_sahara": False,
                "spearhead_1944": False,
                "reaction_forces": False,
                "expeditionary_forces": False
            },
            "server": {
                "hostname": "Arma 3 Server",
                "port": 2302,
                "maxPlayers": 40,
                "serverPassword": "",
                "adminPassword": ""
            }
        }
        
        files_to_check = {
            self.defaults_mods_json(): defaults_template["mods"],
            self.defaults_dlcs_json(): defaults_template["dlcs"],
            self.defaults_server_json(): defaults_template["server"],
        }
        
        for path, template in files_to_check.items():
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(template, indent=2))
                log.info(f"Initialized: {path}")
    
    # === Validation ===
    def validate_structure(self) -> tuple[bool, list[str]]:
        """
        Validiert die Verzeichnisstruktur.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        if not self.server_json.exists():
            errors.append(f"Missing master: {self.server_json}")
        
        if not self.defaults_dir.is_dir():
            errors.append(f"Missing defaults dir: {self.defaults_dir}")
        
        if not self.defaults_mods_json().exists():
            errors.append(f"Missing defaults/mods.json: {self.defaults_mods_json()}")
        
        if not self.defaults_dlcs_json().exists():
            errors.append(f"Missing defaults/dlcs.json: {self.defaults_dlcs_json()}")
        
        return (len(errors) == 0, errors)
