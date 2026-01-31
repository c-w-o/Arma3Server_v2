"""
Tests for variant-based mods configuration and merge semantics.
"""

import pytest
from pathlib import Path
from datetime import datetime
from arma_launcher.config.models_variants import (
    ModEntry,
    ModsBase,
    ModsOverride,
    VariantModsConfig,
    ServerSettings,
    merge_mods_list,
    merge_variant_to_base
)


class TestModEntry:
    """Test ModEntry model."""
    
    def test_mod_entry_minimal(self):
        """ModEntry requires only 'id'."""
        mod = ModEntry(id=123456789)
        assert mod.id == 123456789
        assert mod.name is None
    
    def test_mod_entry_full(self):
        """ModEntry with all fields."""
        mod = ModEntry(
            id=123456789,
            name="CBA_A3",
            version="3.16.0",
            required=True,
            notes="Community Based Addons"
        )
        assert mod.id == 123456789
        assert mod.name == "CBA_A3"
        assert mod.required is True
    
    def test_mod_entry_invalid_id(self):
        """ModEntry rejects invalid IDs."""
        with pytest.raises(ValueError):
            ModEntry(id=0)
        
        with pytest.raises(ValueError):
            ModEntry(id=-1)


class TestModsBase:
    """Test base mods configuration."""
    
    def test_mods_base_minimal(self):
        """ModsBase with only required fields."""
        mods = ModsBase(description="Test")
        assert mods.version == "1.0"
        assert mods.serverMods == []
        assert mods.baseMods == []
    
    def test_mods_base_with_entries(self):
        """ModsBase with mod entries."""
        mods = ModsBase(
            description="Full Config",
            baseMods=[
                ModEntry(id=450814997, name="CBA_A3"),
                ModEntry(id=463939057, name="ACE")
            ]
        )
        assert len(mods.baseMods) == 2


class TestModsOverride:
    """Test override semantics."""
    
    def test_override_added(self):
        """Override with only added mods."""
        override = ModsOverride(
            added=[ModEntry(id=123, name="New Mod")]
        )
        assert len(override.added) == 1
        assert override.removed is None
        assert override.replace is None
    
    def test_override_removed(self):
        """Override with only removed IDs."""
        override = ModsOverride(
            removed=[123, 456]
        )
        assert override.removed == [123, 456]
        assert override.added is None
    
    def test_override_replace(self):
        """Override with complete replacement."""
        override = ModsOverride(
            replace=[ModEntry(id=789, name="Only Mod")]
        )
        assert len(override.replace) == 1
        assert override.added is None
        assert override.removed is None


class TestVariantModsConfig:
    """Test variant-specific configuration."""
    
    def test_variant_minimal(self):
        """Variant with minimal config."""
        variant = VariantModsConfig(
            name="test-variant",
            description="Test"
        )
        assert variant.name == "test-variant"
        assert variant.baseMods is None
    
    def test_variant_with_overrides(self):
        """Variant with multiple overrides."""
        variant = VariantModsConfig(
            name="antistasi-sog",
            baseMods=ModsOverride(
                added=[ModEntry(id=111, name="SOG Mod")]
            ),
            serverMods=ModsOverride(
                removed=[456]
            ),
            clientMods=None  # Use base
        )
        assert variant.baseMods.added[0].id == 111
        assert variant.serverMods.removed == [456]
        assert variant.clientMods is None


class TestMergeMods:
    """Test merge semantics."""
    
    def test_merge_with_none_override(self):
        """Merge with None override uses base."""
        base = [
            ModEntry(id=1, name="Mod1"),
            ModEntry(id=2, name="Mod2")
        ]
        merged = merge_mods_list(base, None)
        assert merged == base
    
    def test_merge_with_replace(self):
        """Merge with 'replace' ignores base."""
        base = [ModEntry(id=1, name="Old")]
        override = ModsOverride(
            replace=[ModEntry(id=999, name="New")]
        )
        merged = merge_mods_list(base, override)
        assert len(merged) == 1
        assert merged[0].id == 999
    
    def test_merge_add_mods(self):
        """Merge adds new mods to base."""
        base = [ModEntry(id=1, name="Base")]
        override = ModsOverride(
            added=[ModEntry(id=2, name="Added")]
        )
        merged = merge_mods_list(base, override)
        assert len(merged) == 2
        assert merged[0].id == 1
        assert merged[1].id == 2
    
    def test_merge_remove_mods(self):
        """Merge removes mods by ID."""
        base = [
            ModEntry(id=1, name="Keep"),
            ModEntry(id=2, name="Remove")
        ]
        override = ModsOverride(removed=[2])
        merged = merge_mods_list(base, override)
        assert len(merged) == 1
        assert merged[0].id == 1
    
    def test_merge_add_and_remove(self):
        """Merge adds and removes in one operation."""
        base = [
            ModEntry(id=1, name="Keep"),
            ModEntry(id=2, name="Remove"),
            ModEntry(id=3, name="Also Keep")
        ]
        override = ModsOverride(
            added=[ModEntry(id=4, name="New")],
            removed=[2]
        )
        merged = merge_mods_list(base, override)
        assert len(merged) == 3
        assert [m.id for m in merged] == [1, 3, 4]


class TestMergeVariantToBase:
    """Test full variant merge into base."""
    
    def test_full_merge(self):
        """Merge complete variant into base configuration."""
        base = ModsBase(
            description="Base Config",
            baseMods=[
                ModEntry(id=1, name="CBA"),
                ModEntry(id=2, name="ACE")
            ],
            serverMods=[
                ModEntry(id=100, name="ServerMod")
            ]
        )
        
        variant = VariantModsConfig(
            name="test-variant",
            baseMods=ModsOverride(
                added=[ModEntry(id=3, name="New")],
                removed=[2]
            ),
            serverMods=None  # Use base
        )
        
        merged = merge_variant_to_base(base, variant)
        
        # baseMods should have: CBA, New (ACE removed)
        assert len(merged.baseMods) == 2
        assert [m.id for m in merged.baseMods] == [1, 3]
        
        # serverMods should be unchanged (None in variant)
        assert len(merged.serverMods) == 1
        assert merged.serverMods[0].id == 100
    
    def test_merge_multiple_overrides(self):
        """Merge variant with multiple category overrides."""
        base = ModsBase(
            description="Base",
            baseMods=[ModEntry(id=1, name="Base1")],
            clientMods=[ModEntry(id=10, name="Client1")],
            serverMods=[ModEntry(id=100, name="Server1")]
        )
        
        variant = VariantModsConfig(
            name="variant",
            baseMods=ModsOverride(
                added=[ModEntry(id=2, name="Base2")]
            ),
            clientMods=ModsOverride(
                replace=[ModEntry(id=999, name="ClientOnly")]
            ),
            serverMods=None
        )
        
        merged = merge_variant_to_base(base, variant)
        
        # Verify each category
        assert len(merged.baseMods) == 2  # Added one
        assert len(merged.clientMods) == 1  # Replaced completely
        assert merged.clientMods[0].id == 999
        assert len(merged.serverMods) == 1  # Unchanged


class TestServerSettings:
    """Test server settings model."""
    
    def test_settings_defaults(self):
        """ServerSettings should have sensible defaults."""
        settings = ServerSettings()
        assert settings.port == 2302
        assert settings.maxPlayers == 64
        assert settings.difficulty == "Regular"
    
    def test_settings_custom(self):
        """ServerSettings with custom values."""
        settings = ServerSettings(
            hostname="My Server",
            port=2305,
            maxPlayers=32,
            useOCAP=True
        )
        assert settings.hostname == "My Server"
        assert settings.port == 2305
        assert settings.useOCAP is True
    
    def test_settings_invalid_port(self):
        """ServerSettings rejects invalid ports."""
        with pytest.raises(ValueError):
            ServerSettings(port=0)
        
        with pytest.raises(ValueError):
            ServerSettings(port=99999)
    
    def test_settings_invalid_max_players(self):
        """ServerSettings rejects invalid max players."""
        with pytest.raises(ValueError):
            ServerSettings(maxPlayers=0)
        
        with pytest.raises(ValueError):
            ServerSettings(maxPlayers=999)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
