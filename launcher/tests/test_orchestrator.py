"""
Tests for Orchestrator integration with new FileConfigStore.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import sys

# Test that the new imports exist
def test_orchestrator_has_correct_imports():
    """Verify orchestrator.py has been updated with new imports."""
    import arma_launcher.orchestrator as orch_mod
    
    # Check old import is gone
    source = orch_mod.__file__
    with open(source, 'r') as f:
        content = f.read()
    
    # Should have new imports
    assert 'from .config import ConfigLayout, ConfigMerger, FileConfigStore' in content
    
    # Should NOT have old import
    assert 'from .config_loader import load_config' not in content


def test_orchestrator_uses_store_in_init():
    """Verify orchestrator.py initializes store in __init__."""
    import arma_launcher.orchestrator as orch_mod
    
    source = orch_mod.__file__
    with open(source, 'r') as f:
        content = f.read()
    
    # Check for store initialization
    assert 'self.store = FileConfigStore' in content


def test_orchestrator_cfg_property_uses_store():
    """Verify cfg property uses store.get_merged_config()."""
    import arma_launcher.orchestrator as orch_mod
    
    source = orch_mod.__file__
    with open(source, 'r') as f:
        content = f.read()
    
    # Check for store usage in cfg property
    assert 'self.store.get_merged_config' in content


# Integration tests (will work once image is rebuilt)

class TestOrchestratorIntegration:
    """Test Orchestrator uses FileConfigStore correctly."""
    
    @pytest.fixture
    def mock_settings(self, tmp_path):
        """Create mock settings with temp directories."""
        mock = Mock()
        mock.arma_root = tmp_path / "arma3"
        mock.arma_binary = tmp_path / "arma3" / "arma3server"
        mock.arma_app_id = 233780
        mock.skip_install = True
        mock.instance_name = "production"
        
        return mock
    
    def test_orchestrator_cfg_property_uses_store(self, mock_settings, tmp_path):
        """Orchestrator.cfg should use store.get_merged_config()."""
        from arma_launcher.orchestrator import Orchestrator
        from arma_launcher.config import FileConfigStore
        
        with patch('arma_launcher.orchestrator.build_layout') as mock_build_layout, \
             patch('arma_launcher.orchestrator.ProcessRunner'):
            
            layout_mock = Mock()
            layout_mock.inst_config = tmp_path / "configs"
            mock_build_layout.return_value = layout_mock
            
            orch = Orchestrator(mock_settings)
            
            # Verify store exists and is correct type
            assert hasattr(orch, 'store')
            assert isinstance(orch.store, FileConfigStore)
    
    def test_cfg_property_uses_store(self, mock_settings, tmp_path):
        """Orchestrator.cfg should call store.get_merged_config()."""
        from arma_launcher.orchestrator import Orchestrator
        
        with patch('arma_launcher.orchestrator.build_layout') as mock_build_layout, \
             patch('arma_launcher.orchestrator.ProcessRunner'), \
             patch('arma_launcher.orchestrator.FileConfigStore') as MockStore:
            
            layout_mock = Mock()
            layout_mock.inst_config = tmp_path / "configs"
            mock_build_layout.return_value = layout_mock
            
            # Setup mock store
            store_instance = Mock()
            store_instance.get_merged_config.return_value = {"hostname": "test"}
            MockStore.return_value = store_instance
            
            orch = Orchestrator(mock_settings)
            cfg = orch.cfg
            
            # Verify store.get_merged_config was called
            store_instance.get_merged_config.assert_called_once()
            assert cfg == {"hostname": "test"}
    
    def test_cfg_property_cached(self, mock_settings, tmp_path):
        """Orchestrator.cfg should cache result."""
        from arma_launcher.orchestrator import Orchestrator
        
        with patch('arma_launcher.orchestrator.build_layout') as mock_build_layout, \
             patch('arma_launcher.orchestrator.ProcessRunner'), \
             patch('arma_launcher.orchestrator.FileConfigStore') as MockStore:
            
            layout_mock = Mock()
            layout_mock.inst_config = tmp_path / "configs"
            mock_build_layout.return_value = layout_mock
            
            # Setup mock store
            store_instance = Mock()
            store_instance.get_merged_config.return_value = {"hostname": "test"}
            MockStore.return_value = store_instance
            
            orch = Orchestrator(mock_settings)
            
            # Access cfg property twice
            cfg1 = orch.cfg
            cfg2 = orch.cfg
            
            # Should only call once (cached)
            store_instance.get_merged_config.assert_called_once()
            assert cfg1 is cfg2


class TestOrchestratorConfigLoading:
    """Test Orchestrator with actual config files."""
    
    @pytest.fixture
    def setup_config_files(self, tmp_path):
        """Create actual config files for testing."""
        config_dir = tmp_path / "configs" / "production"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create defaults
        defaults_dir = config_dir / "defaults"
        defaults_dir.mkdir(exist_ok=True)
        
        # defaults.json
        (defaults_dir / "defaults.json").write_text("""{
            "version": "1.0",
            "hostname": "Default Server",
            "password": "",
            "admin_password": "default"
        }""")
        
        # Create override
        override_dir = config_dir / "overrides" / "production"
        override_dir.mkdir(parents=True, exist_ok=True)
        
        (override_dir / "override.json").write_text("""{
            "hostname": "My Production Server"
        }""")
        
        return config_dir


class TestOrchestratorUsesCorrectConfigName:
    """Test that Orchestrator uses the right active config."""
    
    def test_active_config_name_from_settings(self):
        """TODO: cfg property should read active config name from settings."""
        # Currently hardcoded to "production"
        # This should be enhanced to read from settings.instance_name or a config file
        pass
    
    def test_active_config_name_fallback(self):
        """TODO: If no active config set, should default to 'production'."""
        pass
