"""
New API endpoints for variant-based mods configuration.

Endpoints:
- GET  /api/defaults/mods          - Get base mods configuration
- GET  /api/variants               - List all variants
- GET  /api/variants/{name}        - Get specific variant (merged)
- POST /api/variants               - Create new variant
- PUT  /api/variants/{name}/mods   - Update variant mods (atomic)
- DELETE /api/variants/{name}      - Delete variant
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
import json
from datetime import datetime

from .config.file_layout import ConfigLayout
from .config.models_variants import (
    ModsBase,
    VariantModsConfig,
    ServerSettings,
    merge_variant_to_base,
    merge_mods_list
)
from .config_loader import load_json, save_json
from .settings import Settings


class VariantsAPI:
    """API handlers for variant-based configuration."""
    
    def __init__(self, settings: Settings, config_layout: ConfigLayout):
        self.settings = settings
        self.layout = config_layout
    
    def _load_base_mods(self) -> ModsBase:
        """Load base mods configuration."""
        mods_path = self.layout.defaults_mods_json()
        if not mods_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Base mods not found at {mods_path}"
            )
        
        try:
            data = load_json(mods_path)
            return ModsBase.model_validate(data)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading base mods: {str(e)}"
            )
    
    def _load_server_settings(self) -> ServerSettings:
        """Load global server settings."""
        settings_path = self.layout.inst_config / "server-settings.json"
        if not settings_path.exists():
            return ServerSettings()  # Return defaults
        
        try:
            data = load_json(settings_path)
            return ServerSettings.model_validate(data)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading server settings: {str(e)}"
            )
    
    def _load_variant(self, name: str) -> VariantModsConfig:
        """Load specific variant configuration."""
        variant_dir = self.layout.variants_dir / name
        mods_path = variant_dir / "mods.json"
        
        if not mods_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Variant '{name}' not found"
            )
        
        try:
            data = load_json(mods_path)
            return VariantModsConfig.model_validate(data)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error parsing variant '{name}': {str(e)}"
            )
    
    def _list_variants(self) -> list[str]:
        """List all available variant names."""
        variants_dir = self.layout.variants_dir
        if not variants_dir.exists():
            return []
        
        return [
            d.name for d in variants_dir.iterdir()
            if d.is_dir() and (d / "mods.json").exists()
        ]
    
    # ========================================================================
    # API Handlers
    # ========================================================================
    
    def get_defaults_mods(self) -> dict:
        """GET /api/defaults/mods - Get base mods configuration."""
        base = self._load_base_mods()
        return {
            "ok": True,
            "data": base.model_dump()
        }
    
    def get_variants(self) -> dict:
        """GET /api/variants - List all variants with basic info."""
        variants = self._list_variants()
        
        result = []
        for name in variants:
            try:
                variant = self._load_variant(name)
                result.append({
                    "name": name,
                    "description": variant.description,
                    "lastModified": variant.lastModified.isoformat() if variant.lastModified else None
                })
            except HTTPException:
                # Skip variants that can't be loaded
                pass
        
        return {
            "ok": True,
            "data": result
        }
    
    def get_variant(self, name: str) -> dict:
        """GET /api/variants/{name} - Get specific variant (merged with base)."""
        base = self._load_base_mods()
        variant = self._load_variant(name)
        
        # Merge variant into base
        merged = merge_variant_to_base(base, variant)
        
        return {
            "ok": True,
            "data": {
                "name": name,
                "description": variant.description,
                "base": base.model_dump(),
                "override": variant.model_dump(),
                "merged": merged.model_dump(),
                "lastModified": variant.lastModified.isoformat() if variant.lastModified else None
            }
        }
    
    def create_variant(self, name: str, payload: dict) -> dict:
        """POST /api/variants - Create new variant."""
        # Check if variant already exists
        existing = self._list_variants()
        if name in existing:
            raise HTTPException(
                status_code=409,
                detail=f"Variant '{name}' already exists"
            )
        
        # Create variant directory
        variant_dir = self.layout.variants_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mods.json
        mods_data = {
            "version": "1.0",
            "name": name,
            "description": payload.get("description", ""),
            "lastModified": datetime.now().isoformat(),
            "modifiedBy": payload.get("modifiedBy", "api")
        }
        
        mods_path = variant_dir / "mods.json"
        try:
            save_json(mods_path, mods_data)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating variant: {str(e)}"
            )
        
        # Create metadata.json
        metadata_data = {
            "createdAt": datetime.now().isoformat(),
            "lastModified": datetime.now().isoformat(),
            "modifiedBy": payload.get("modifiedBy", "api"),
            "description": payload.get("description")
        }
        
        metadata_path = variant_dir / "metadata.json"
        try:
            save_json(metadata_path, metadata_data)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating variant metadata: {str(e)}"
            )
        
        return {
            "ok": True,
            "data": {
                "name": name,
                "created": True
            }
        }
    
    def update_variant_mods(self, name: str, payload: dict) -> dict:
        """PUT /api/variants/{name}/mods - Update variant mods (atomic)."""
        # Load existing variant
        try:
            variant = self._load_variant(name)
        except HTTPException:
            # Create new if doesn't exist
            variant = VariantModsConfig(name=name)
        
        # Validate payload structure
        try:
            update_data = VariantModsConfig.model_validate(payload)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid variant configuration: {str(e)}"
            )
        
        # Update fields
        variant.serverMods = update_data.serverMods
        variant.baseMods = update_data.baseMods
        variant.clientMods = update_data.clientMods
        variant.maps = update_data.maps
        variant.missionMods = update_data.missionMods
        variant.extraServer = update_data.extraServer
        variant.extraBase = update_data.extraBase
        variant.extraClient = update_data.extraClient
        variant.extraMaps = update_data.extraMaps
        variant.extraMission = update_data.extraMission
        variant.minus_mods = update_data.minus_mods
        
        variant.lastModified = datetime.now()
        variant.modifiedBy = payload.get("modifiedBy", "api")
        
        # Save atomically
        variant_dir = self.layout.variants_dir / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        
        mods_path = variant_dir / "mods.json"
        try:
            save_json(mods_path, variant.model_dump())
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error saving variant mods: {str(e)}"
            )
        
        # Load base to return merged config
        base = self._load_base_mods()
        merged = merge_variant_to_base(base, variant)
        
        return {
            "ok": True,
            "data": {
                "name": name,
                "merged": merged.model_dump(),
                "lastModified": variant.lastModified.isoformat()
            }
        }
    
    def delete_variant(self, name: str) -> dict:
        """DELETE /api/variants/{name} - Delete variant."""
        variant_dir = self.layout.variants_dir / name
        
        if not variant_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Variant '{name}' not found"
            )
        
        # Delete directory
        import shutil
        try:
            shutil.rmtree(variant_dir)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting variant: {str(e)}"
            )
        
        return {
            "ok": True,
            "data": {
                "name": name,
                "deleted": True
            }
        }


def register_variants_routes(app, settings: Settings, config_layout: ConfigLayout):
    """Register variant routes to FastAPI app."""
    api = VariantsAPI(settings, config_layout)
    router = APIRouter(prefix="/api", tags=["variants"])
    
    # Defaults
    @router.get("/defaults/mods")
    def get_defaults_mods():
        """Get base mods configuration."""
        return api.get_defaults_mods()
    
    # Variants
    @router.get("/variants")
    def get_variants():
        """List all variants."""
        return api.get_variants()
    
    @router.get("/variants/{name}")
    def get_variant(name: str):
        """Get specific variant (merged with base)."""
        return api.get_variant(name)
    
    @router.post("/variants")
    def create_variant(
        name: str = Query(..., description="Variant name"),
        payload: dict = None
    ):
        """Create new variant."""
        if payload is None:
            payload = {}
        return api.create_variant(name, payload)
    
    @router.put("/variants/{name}/mods")
    def update_variant_mods(name: str, payload: dict):
        """Update variant mods (atomic)."""
        return api.update_variant_mods(name, payload)
    
    @router.delete("/variants/{name}")
    def delete_variant(name: str):
        """Delete variant."""
        return api.delete_variant(name)
    
    app.include_router(router)
