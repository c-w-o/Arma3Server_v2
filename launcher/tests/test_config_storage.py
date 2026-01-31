"""
Unit-Tests für Config Storage & Merge Logic.

Dieses Test-Modul validiert die neuen Module:
- storage_backend.py
- file_layout.py
- merger.py
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from arma_launcher.config.file_layout import ConfigLayout
from arma_launcher.config.merger import ConfigMerger
from arma_launcher.config.storage_backend import FileConfigStore
from arma_launcher.models_file import (
    FileConfig_Defaults,
    FileConfig_Override,
    FileConfig_Mods,
    FileConfig_Dlcs,
    FileConfig_ModEntry,
    FileConfig_Admin,
)


@pytest.fixture
def temp_config_dir():
    """Erstellt tempisches Config-Verzeichnis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config_layout(temp_config_dir):
    """Erstellt initialisiertes ConfigLayout."""
    layout = ConfigLayout(temp_config_dir / "config")
    layout.ensure_structure()
    return layout


class TestConfigLayout:
    """Tests für Verzeichnisstruktur."""
    
    def test_ensure_structure_creates_directories(self, temp_config_dir):
        """Testet dass ensure_structure alle Verzeichnisse erstellt."""
        layout = ConfigLayout(temp_config_dir / "config")
        layout.ensure_structure()
        
        assert layout.defaults_dir.exists()
        assert layout.configs_dir.exists()
        assert layout.cache_dir.exists()
        assert layout.server_json.exists()
    
    def test_defaults_paths(self, config_layout):
        """Testet dass Standard-Pfade korrekt sind."""
        assert config_layout.defaults_mods_json().exists()
        assert config_layout.defaults_dlcs_json().exists()
        assert config_layout.defaults_server_json().exists()
    
    def test_config_dir_paths(self, config_layout):
        """Testet dass Config-Pfade korrekt sind."""
        config_name = "production"
        cfg_dir = config_layout.config_dir(config_name)
        
        assert cfg_dir.parent == config_layout.configs_dir
        assert config_layout.config_metadata_json(config_name).parent == cfg_dir
        assert config_layout.config_mods_json(config_name).parent == cfg_dir
    
    def test_validate_structure(self, config_layout):
        """Testet Struktur-Validierung."""
        is_valid, errors = config_layout.validate_structure()
        assert is_valid
        assert len(errors) == 0


class TestConfigMerger:
    """Tests für Merge-Logik."""
    
    @pytest.fixture
    def merger(self):
        return ConfigMerger()
    
    @pytest.fixture
    def defaults(self):
        """Erstellt Standard-Defaults."""
        return FileConfig_Defaults(
            maxPlayers=40,
            hostname="Default Server",
            serverPassword="",
            adminPassword="admin",
            serverCommandPassword="",
            port=2302,
            mods=FileConfig_Mods(
                serverMods=[FileConfig_ModEntry(name="TestMod", id=123)],
                baseMods=[FileConfig_ModEntry(name="BaseMod", id=456)],
            ),
            dlcs=FileConfig_Dlcs(contact=False, csla_iron_curtain=False),
        )
    
    def test_merge_with_empty_override(self, merger, defaults):
        """Testet dass leerer Override die Defaults behält."""
        override = FileConfig_Override()
        result = merger.merge(defaults, override)
        
        assert result.maxPlayers == 40
        assert result.hostname == "Default Server"
        assert len(result.mods.serverMods) == 1
    
    def test_merge_with_partial_override(self, merger, defaults):
        """Testet dass Override nur die Felder ändert, die gesetzt sind."""
        override = FileConfig_Override(
            maxPlayers=50,
            hostname="Custom Server"
        )
        result = merger.merge(defaults, override)
        
        assert result.maxPlayers == 50
        assert result.hostname == "Custom Server"
        assert result.port == 2302  # Unverändert
    
    def test_merge_mods_empty_list_replaces(self, merger):
        """Testet dass leere Mod-Listen die Defaults ersetzen."""
        default_mods = FileConfig_Mods(
            baseMods=[FileConfig_ModEntry(name="Mod1", id=1), FileConfig_ModEntry(name="Mod2", id=2)]
        )
        override_mods = FileConfig_Mods(baseMods=[])  # Explizit leer
        
        result = merger.merge_mods(default_mods, override_mods)
        assert len(result.baseMods) == 0
    
    def test_merge_mods_none_keeps_default(self, merger):
        """Testet dass None-Mods die Defaults behält."""
        default_mods = FileConfig_Mods(
            baseMods=[FileConfig_ModEntry(name="Mod1", id=1)]
        )
        override_mods = FileConfig_Mods(baseMods=None)
        
        result = merger.merge_mods(default_mods, override_mods)
        assert len(result.baseMods) == 1
        assert result.baseMods[0].id == 1
    
    def test_merge_mods_override_replaces(self, merger):
        """Testet dass Override-Mods die Defaults ersetzen."""
        default_mods = FileConfig_Mods(
            baseMods=[FileConfig_ModEntry(name="Mod1", id=1)]
        )
        override_mods = FileConfig_Mods(
            baseMods=[FileConfig_ModEntry(name="NewMod", id=999)]
        )
        
        result = merger.merge_mods(default_mods, override_mods)
        assert len(result.baseMods) == 1
        assert result.baseMods[0].id == 999
    
    def test_merge_dlcs(self, merger):
        """Testet DLC-Merge."""
        default_dlcs = FileConfig_Dlcs(contact=False)
        override_dlcs = FileConfig_Dlcs(contact=True)
        
        result = merger.merge_dlcs(default_dlcs, override_dlcs)
        assert result.contact == True
    
    def test_compute_delta(self, merger, defaults):
        """Testet Delta-Berechnung."""
        merged = FileConfig_Defaults(
            maxPlayers=50,
            hostname="Custom",
            serverPassword="",
            adminPassword="admin",
            serverCommandPassword="",
            port=2302,
            mods=FileConfig_Mods(
                serverMods=[FileConfig_ModEntry(name="TestMod", id=123)],
                baseMods=[],  # Change
            ),
            dlcs=FileConfig_Dlcs(contact=True, csla_iron_curtain=False),  # Change
        )
        
        delta = merger.compute_delta(defaults, merged)
        
        assert delta["/maxPlayers"]["merged"] == 50
        assert delta["/hostname"]["merged"] == "Custom"
        assert "/mods" in delta
        assert "/dlcs" in delta


class TestFileConfigStore:
    """Tests für FileConfigStore."""
    
    @pytest.fixture
    def store(self, config_layout):
        merger = ConfigMerger()
        return FileConfigStore(config_layout, merger)
    
    def test_load_defaults(self, store):
        """Testet Laden von Defaults."""
        defaults = store.load_defaults()
        assert defaults.maxPlayers > 0
        assert isinstance(defaults.mods, FileConfig_Mods)
    
    def test_create_and_load_config(self, store):
        """Testet Erstellen und Laden einer Config."""
        store.create_config("test-config", description="Test Config")
        
        configs = store.list_configs()
        assert "test-config" in configs
        
        metadata = store.get_metadata("test-config")
        assert metadata.name == "test-config"
        assert metadata.description == "Test Config"
    
    def test_set_and_get_active_config(self, store):
        """Testet Setzen der aktiven Config."""
        store.create_config("production")
        store.create_config("staging")
        
        store.set_active_config("staging")
        assert store.get_active_config() == "staging"
    
    def test_save_and_load_override(self, store):
        """Testet Speichern und Laden von Overrides."""
        store.create_config("test")
        
        override = FileConfig_Override(
            hostname="Test Server",
            maxPlayers=100,
            mods=FileConfig_Mods(
                baseMods=[FileConfig_ModEntry(name="TestMod", id=789)]
            )
        )
        
        store.save_override("test", override, modified_by="test_user")
        loaded = store.load_override("test")
        
        assert loaded.hostname == "Test Server"
        assert loaded.maxPlayers == 100
        assert len(loaded.mods.baseMods) == 1
    
    def test_get_merged_config(self, store):
        """Testet Merge von Defaults + Override."""
        store.create_config("prod")
        
        override = FileConfig_Override(maxPlayers=64)
        store.save_override("prod", override)
        
        merged = store.get_merged_config("prod")
        assert merged.maxPlayers == 64
    
    def test_delete_config_fails_if_active(self, store):
        """Testet dass aktive Config nicht gelöscht werden kann."""
        store.create_config("production")
        store.set_active_config("production")
        
        with pytest.raises(ValueError, match="Cannot delete active config"):
            store.delete_config("production")
    
    def test_delete_config_succeeds_if_not_active(self, store):
        """Testet dass inaktive Config gelöscht werden kann."""
        store.create_config("production")
        store.create_config("staging")
        
        store.set_active_config("production")
        store.delete_config("staging")
        
        assert "staging" not in store.list_configs()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
