"""
Pydantic models for variant-based mods configuration with JSON Schema validation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ModEntry(BaseModel):
    """Single mod entry with Steam ID and metadata."""
    id: int = Field(..., gt=0, description="Steam Workshop ID or custom identifier")
    name: Optional[str] = None
    version: Optional[str] = None
    required: bool = False
    notes: Optional[str] = None


class ModsBase(BaseModel):
    """Full mods configuration (all 11 categories)."""
    version: str = "1.0"
    description: str
    serverMods: List[ModEntry] = []
    baseMods: List[ModEntry] = []
    clientMods: List[ModEntry] = []
    maps: List[ModEntry] = []
    missionMods: List[ModEntry] = []
    extraServer: List[ModEntry] = []
    extraBase: List[ModEntry] = []
    extraClient: List[ModEntry] = []
    extraMaps: List[ModEntry] = []
    extraMission: List[ModEntry] = []
    minus_mods: List[ModEntry] = []
    
    lastModified: Optional[datetime] = None
    modifiedBy: Optional[str] = None


class ModsOverride(BaseModel):
    """Override semantics: added/removed/replace for variant configurations."""
    added: Optional[List[ModEntry]] = None
    removed: Optional[List[int]] = None  # List of mod IDs to remove
    replace: Optional[List[ModEntry]] = None  # Complete replacement


class VariantModsConfig(BaseModel):
    """Variant-specific mods override (with null/added/removed/replace semantics)."""
    version: str = "1.0"
    name: str
    description: Optional[str] = None
    
    serverMods: Optional[ModsOverride] = None
    baseMods: Optional[ModsOverride] = None
    clientMods: Optional[ModsOverride] = None
    maps: Optional[ModsOverride] = None
    missionMods: Optional[ModsOverride] = None
    extraServer: Optional[ModsOverride] = None
    extraBase: Optional[ModsOverride] = None
    extraClient: Optional[ModsOverride] = None
    extraMaps: Optional[ModsOverride] = None
    extraMission: Optional[ModsOverride] = None
    minus_mods: Optional[ModsOverride] = None
    
    lastModified: Optional[datetime] = None
    modifiedBy: Optional[str] = None


class ServerSettings(BaseModel):
    """Server configuration settings."""
    version: str = "1.0"
    hostname: Optional[str] = None
    port: int = 2302
    maxPlayers: int = 64
    password: Optional[str] = ""
    serverCommandPassword: Optional[str] = None
    adminPassword: Optional[str] = None
    difficulty: str = "Regular"
    world: str = "empty"
    useOCAP: bool = False
    numHeadless: int = 0
    
    lastModified: Optional[datetime] = None
    modifiedBy: Optional[str] = None
    
    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return v
    
    @field_validator("maxPlayers")
    @classmethod
    def validate_max_players(cls, v):
        if not (1 <= v <= 127):
            raise ValueError("maxPlayers must be between 1 and 127")
        return v


class VariantMetadata(BaseModel):
    """Metadata for a variant (created, modified, author, etc.)."""
    createdAt: datetime
    lastModified: datetime
    modifiedBy: str
    createdBy: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class VariantConfig(BaseModel):
    """Complete variant configuration (mods + metadata)."""
    name: str
    mods: VariantModsConfig
    settings: Optional[ServerSettings] = None
    metadata: VariantMetadata


# ============================================================================
# Merge Helpers
# ============================================================================

def merge_mods_list(base: List[ModEntry], override: Optional[ModsOverride]) -> List[ModEntry]:
    """
    Merge base mods list with variant override.
    
    Semantics:
    - None/missing: use base
    - { "replace": [...] }: complete replacement
    - { "added": [...], "removed": [...] }: additive merge
    """
    if override is None:
        return base
    
    if override.replace is not None:
        return override.replace
    
    result = list(base)  # Copy
    
    # Remove mods by ID
    if override.removed:
        removed_ids = set(override.removed)
        result = [m for m in result if m.id not in removed_ids]
    
    # Add new mods
    if override.added:
        result.extend(override.added)
    
    return result


def merge_variant_to_base(base: ModsBase, variant: VariantModsConfig) -> ModsBase:
    """
    Merge variant override into base mods, producing a complete mods configuration.
    """
    merged = ModsBase(
        version="1.0",
        description=f"{base.description} (variant: {variant.name})",
        serverMods=merge_mods_list(base.serverMods, variant.serverMods),
        baseMods=merge_mods_list(base.baseMods, variant.baseMods),
        clientMods=merge_mods_list(base.clientMods, variant.clientMods),
        maps=merge_mods_list(base.maps, variant.maps),
        missionMods=merge_mods_list(base.missionMods, variant.missionMods),
        extraServer=merge_mods_list(base.extraServer, variant.extraServer),
        extraBase=merge_mods_list(base.extraBase, variant.extraBase),
        extraClient=merge_mods_list(base.extraClient, variant.extraClient),
        extraMaps=merge_mods_list(base.extraMaps, variant.extraMaps),
        extraMission=merge_mods_list(base.extraMission, variant.extraMission),
        minus_mods=merge_mods_list(base.minus_mods, variant.minus_mods),
        lastModified=datetime.now(),
        modifiedBy="merger"
    )
    return merged
