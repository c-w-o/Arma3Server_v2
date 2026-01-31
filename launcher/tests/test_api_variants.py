"""
Tests for Variant API endpoints.
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import json

from arma_launcher.api_variants import VariantsAPI
from arma_launcher.config.file_layout import ConfigLayout
from arma_launcher.config.models_variants import (
    ModEntry,
    ModsBase,
    ModsOverride,
    VariantModsConfig,
    ServerSettings
)


class TestVariantsAPI:
    """Test VariantsAPI class."""
    
    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create temporary config directory structure."""
        config_dir = tmp_path / "config"
        defaults_dir = config_dir / "defaults"
        variants_dir = config_dir / "variants"
        
        defaults_dir.mkdir(parents=True)
        variants_dir.mkdir(parents=True)
        
        # Create base mods file
        base_mods = {
            "version": "1.0",
            "description": "Base mods",
            "serverMods": [{"id": 1, "name": "ServerMod1"}],
            "baseMods": [{"id": 2, "name": "BaseMod1"}],
            "clientMods": [],
            "maps": [],
            "missionMods": [],
            "extraServer": [],
            "extraBase": [],
            "extraClient": [],
            "extraMaps": [],
            "extraMission": [],
            "minus_mods": []
        }
        
        with open(defaults_dir / "mods.json", "w") as f:
            json.dump(base_mods, f)
        
        return config_dir
    
    @pytest.fixture
    def config_layout(self, temp_config_dir):
        """Create ConfigLayout instance."""
        return ConfigLayout(temp_config_dir)
    
    @pytest.fixture
    def settings_mock(self):
        """Create mock Settings."""
        return Mock()
    
    @pytest.fixture
    def api(self, settings_mock, config_layout):
        """Create VariantsAPI instance."""
        return VariantsAPI(settings_mock, config_layout)
    
    def test_load_base_mods(self, api):
        """Test loading base mods configuration."""
        base = api._load_base_mods()
        
        assert base.description == "Base mods"
        assert len(base.serverMods) == 1
        assert base.serverMods[0].id == 1
    
    def test_load_base_mods_not_found(self, api, tmp_path):
        """Test error when base mods not found."""
        empty_layout = ConfigLayout(tmp_path / "empty")
        empty_layout.defaults_dir.mkdir(parents=True)
        api.layout = empty_layout
        
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            api._load_base_mods()
        assert exc.value.status_code == 404
    
    def test_list_variants_empty(self, api):
        """Test listing variants when none exist."""
        variants = api._list_variants()
        assert variants == []
    
    def test_list_variants(self, api, tmp_path):
        """Test listing multiple variants."""
        # Create some variants
        variant1_dir = api.layout.variants_dir / "variant1"
        variant2_dir = api.layout.variants_dir / "variant2"
        
        for vdir in [variant1_dir, variant2_dir]:
            vdir.mkdir(parents=True)
            with open(vdir / "mods.json", "w") as f:
                json.dump({"version": "1.0", "name": vdir.name}, f)
        
        variants = api._list_variants()
        assert len(variants) == 2
        assert "variant1" in variants
        assert "variant2" in variants
    
    def test_create_variant(self, api):
        """Test creating a new variant."""
        result = api.create_variant("test-variant", {
            "description": "Test Variant"
        })
        
        assert result["ok"] is True
        assert result["data"]["name"] == "test-variant"
        
        # Verify files were created
        assert (api.layout.variant_mods_json("test-variant")).exists()
        assert (api.layout.variant_metadata_json("test-variant")).exists()
    
    def test_create_variant_already_exists(self, api):
        """Test error when creating duplicate variant."""
        # Create first
        api.create_variant("test", {"description": "First"})
        
        # Try to create again
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            api.create_variant("test", {"description": "Second"})
        assert exc.value.status_code == 409
    
    def test_get_variant(self, api):
        """Test getting specific variant (merged)."""
        # Create variant
        api.create_variant("test-variant", {
            "description": "Test"
        })
        
        # Write variant config with override
        variant_config = {
            "version": "1.0",
            "name": "test-variant",
            "baseMods": {
                "added": [{"id": 3, "name": "NewMod"}]
            }
        }
        
        with open(api.layout.variant_mods_json("test-variant"), "w") as f:
            json.dump(variant_config, f)
        
        # Get merged
        result = api.get_variant("test-variant")
        
        assert result["ok"] is True
        assert result["data"]["name"] == "test-variant"
        assert "base" in result["data"]
        assert "override" in result["data"]
        assert "merged" in result["data"]
        
        # Verify merge happened
        merged = result["data"]["merged"]
        assert len(merged["baseMods"]) == 2  # Original + new
    
    def test_get_variant_not_found(self, api):
        """Test error when variant not found."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            api.get_variant("nonexistent")
        assert exc.value.status_code == 404
    
    def test_update_variant_mods(self, api):
        """Test updating variant mods."""
        # Create variant
        api.create_variant("test", {"description": "Test"})
        
        # Update with new override
        update_payload = {
            "version": "1.0",
            "name": "test",
            "baseMods": {
                "added": [{"id": 999, "name": "NewMod"}]
            }
        }
        
        result = api.update_variant_mods("test", update_payload)
        
        assert result["ok"] is True
        assert "merged" in result["data"]
        
        # Verify file was updated
        with open(api.layout.variant_mods_json("test")) as f:
            saved = json.load(f)
        assert saved["baseMods"]["added"][0]["id"] == 999
    
    def test_delete_variant(self, api):
        """Test deleting a variant."""
        # Create variant
        api.create_variant("test", {"description": "Test"})
        assert api.layout.variant_dir("test").exists()
        
        # Delete
        result = api.delete_variant("test")
        
        assert result["ok"] is True
        assert not api.layout.variant_dir("test").exists()
    
    def test_delete_variant_not_found(self, api):
        """Test error when deleting nonexistent variant."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            api.delete_variant("nonexistent")
        assert exc.value.status_code == 404
    
    def test_get_defaults_mods(self, api):
        """Test getting defaults mods endpoint response."""
        result = api.get_defaults_mods()
        
        assert result["ok"] is True
        assert "data" in result
        data = result["data"]
        assert data["description"] == "Base mods"
    
    def test_get_variants_list(self, api):
        """Test getting variants list endpoint response."""
        # Create some variants
        api.create_variant("variant1", {"description": "Variant 1"})
        api.create_variant("variant2", {"description": "Variant 2"})
        
        result = api.get_variants()
        
        assert result["ok"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] in ["variant1", "variant2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
