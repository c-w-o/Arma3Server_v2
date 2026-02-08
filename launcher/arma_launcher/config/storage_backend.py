"""
Multi-File Konfigurations-Persistierung für Green-Field Setup.

Zentrale Storage-Schicht für die neue Architektur.
Keine Backwards-Compatibility nötig (kein Produktionsbetrieb).
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, List
import json
from datetime import datetime, timezone
from pydantic import BaseModel

from .file_layout import ConfigLayout
from ..models_file import (
    FileConfig_Defaults,
    FileConfig_Override,
    FileConfig_Mods,
    FileConfig_Dlcs,
)
from .merger import ConfigMerger
from ..logging_setup import get_logger

log = get_logger("arma.config.storage")


class ConfigMetadata(BaseModel):
    """Metadaten für eine Konfiguration."""
    name: str
    description: Optional[str] = None
    createdAt: datetime
    lastModified: datetime
    modifiedBy: str = "system"
    version: int = 1


class FileConfigStore:
    """
    Multi-File Persistierung für grüne Wiese (kein Produktionsbetrieb).
    
    Struktur:
        config/
        ├── server.json (master)
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
            └── ...
    """
    
    def __init__(self, layout: ConfigLayout, merger: ConfigMerger):
        self.layout = layout
        self.merger = merger
        self.layout.ensure_structure()  # Erstelle Verzeichnisse
    
    def _load_json(self, path: Path) -> Dict:
        """Lädt JSON-Datei mit Error-Handling."""
        if not path.exists():
            log.warning(f"Config file not found: {path}")
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Failed to load {path}: {e}")
            raise
    
    def _save_json(self, path: Path, data: Dict) -> None:
        """Speichert JSON-Datei atomar."""
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: Schreibe zu temp, dann rename
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_path.replace(path)
        log.info(f"Saved config: {path}")
    
    def load_defaults(self) -> FileConfig_Defaults:
        """Lädt defaults/mods.json + defaults/dlcs.json etc."""
        raw_mods = self._load_json(self.layout.defaults_mods_json())
        raw_dlcs = self._load_json(self.layout.defaults_dlcs_json())
        raw_server = self._load_json(self.layout.defaults_server_json())
        
        # Zusammensetzen in FileConfig_Defaults
        merged_raw = {
            **raw_server,
            "mods": FileConfig_Mods.model_validate(raw_mods),
            "dlcs": FileConfig_Dlcs.model_validate(raw_dlcs),
        }
        return FileConfig_Defaults.model_validate(merged_raw)
    
    def save_defaults(
        self, 
        mods: Optional[FileConfig_Mods] = None, 
        dlcs: Optional[FileConfig_Dlcs] = None,
        server_settings: Optional[Dict] = None
    ) -> None:
        """Speichert defaults/mods.json und/oder defaults/dlcs.json."""
        if mods is not None:
            self._save_json(
                self.layout.defaults_mods_json(),
                mods.model_dump(mode="json", by_alias=True, exclude_none=True)
            )
        
        if dlcs is not None:
            self._save_json(
                self.layout.defaults_dlcs_json(),
                dlcs.model_dump(mode="json", by_alias=True, exclude_none=True)
            )
        
        if server_settings is not None:
            self._save_json(self.layout.defaults_server_json(), server_settings)
        
        log.info(f"Saved defaults: mods={mods is not None}, dlcs={dlcs is not None}, server={server_settings is not None}")
    
    def load_override(self, name: str) -> FileConfig_Override:
        """Lädt configs/{name}/mods.json etc."""
        cfg_dir = self.layout.config_dir(name)
        if not cfg_dir.exists():
            log.warning(f"Config dir not found: {cfg_dir}")
            return FileConfig_Override()
        
        raw_mods = self._load_json(cfg_dir / "mods.json")
        raw_dlcs = self._load_json(cfg_dir / "dlcs.json")
        raw_server = self._load_json(cfg_dir / "server.json")
        
        merged_raw = {
            "mods": FileConfig_Mods.model_validate(raw_mods) if raw_mods else None,
            "dlcs": FileConfig_Dlcs.model_validate(raw_dlcs) if raw_dlcs else None,
            **raw_server,
        }
        return FileConfig_Override.model_validate(merged_raw)
    
    def save_override(self, name: str, override: FileConfig_Override, modified_by: str = "system") -> None:
        """Speichert Overrides zu configs/{name}/*.json"""
        cfg_dir = self.layout.config_dir(name)
        cfg_dir.mkdir(parents=True, exist_ok=True)
        
        # Metadata aktualisieren
        metadata = self.get_metadata(name)
        metadata.lastModified = datetime.now(timezone.utc)
        metadata.modifiedBy = modified_by
        metadata.version += 1
        
        self._save_json(cfg_dir / "metadata.json", metadata.model_dump(mode="json"))
        
        # Einzelne Dateien speichern
        if override.mods:
            self._save_json(cfg_dir / "mods.json", override.mods.model_dump(mode="json", by_alias=True))
        if override.dlcs:
            self._save_json(cfg_dir / "dlcs.json", override.dlcs.model_dump(mode="json", by_alias=True))
        
        # Server-Settings
        server_data = override.model_dump(
            exclude={"mods", "dlcs"},
            exclude_none=True,
            mode="json"
        )
        if server_data:
            self._save_json(cfg_dir / "server.json", server_data)
    
    def list_configs(self) -> List[str]:
        """Listet alle configs/{name}/ Verzeichnisse."""
        configs_dir = self.layout.configs_dir
        if not configs_dir.exists():
            return []
        return [d.name for d in configs_dir.iterdir() if d.is_dir() and (d / "metadata.json").exists()]
    
    def get_active_config(self) -> str:
        """Liest activeConfig aus server.json."""
        raw = self._load_json(self.layout.server_json)
        return raw.get("activeConfig", "production")
    
    def set_active_config(self, name: str) -> None:
        """Schreibt activeConfig zu server.json."""
        if name not in self.list_configs():
            raise ValueError(f"Config not found: {name}")
        
        raw = self._load_json(self.layout.server_json)
        raw["activeConfig"] = name
        raw["lastModified"] = datetime.now(timezone.utc).isoformat()
        self._save_json(self.layout.server_json, raw)
    
    def get_metadata(self, name: str) -> ConfigMetadata:
        """Liest configs/{name}/metadata.json."""
        metadata_path = self.layout.config_dir(name) / "metadata.json"
        raw = self._load_json(metadata_path)
        
        if not raw:
            # Fallback: Erstelle Default-Metadata
            return ConfigMetadata(
                name=name,
                createdAt=datetime.now(timezone.utc),
                lastModified=datetime.now(timezone.utc),
            )
        
        return ConfigMetadata.model_validate(raw)
    
    def create_config(
        self,
        name: str,
        description: str = "",
        base_config: Optional[str] = None,
        modified_by: str = "system"
    ) -> None:
        """Erstellt neue Konfiguration."""
        if name in self.list_configs():
            raise ValueError(f"Config already exists: {name}")
        
        cfg_dir = self.layout.config_dir(name)
        cfg_dir.mkdir(parents=True, exist_ok=True)
        
        # Metadata
        metadata = ConfigMetadata(
            name=name,
            description=description,
            createdAt=datetime.now(timezone.utc),
            lastModified=datetime.now(timezone.utc),
            modifiedBy=modified_by,
            version=1,
        )
        self._save_json(cfg_dir / "metadata.json", metadata.model_dump(mode="json"))
        
        # Leere/Basis-Overrides
        override = FileConfig_Override(description=description)
        self.save_override(name, override, modified_by=modified_by)
        
        log.info(f"Created config: {name}")
    
    def delete_config(self, name: str) -> None:
        """Löscht Konfiguration (mit Sicherheit gegen active config)."""
        if self.get_active_config() == name:
            raise ValueError(f"Cannot delete active config: {name}")
        
        cfg_dir = self.layout.config_dir(name)
        import shutil
        shutil.rmtree(cfg_dir, ignore_errors=True)
        log.info(f"Deleted config: {name}")
    
    def get_merged_config(self, name: str) -> FileConfig_Defaults:
        """
        Merged Defaults + Override für eine Config.
        
        Dies ist die zentrale Merge-Funktion.
        """
        defaults = self.load_defaults()
        override = self.load_override(name)
        return self.merger.merge(defaults, override)
