# arma_launcher_next/models_FileConfig_.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, AliasChoices, ConfigDict


class FileConfig_Admin(BaseModel):
    name: str
    steamid: str


class FileConfig_ModEntry(BaseModel):
    name: str
    id: int

class FileConfig_CustomMods(BaseModel):
    mods: List[str] = Field(default_factory=list)
    serverMods: List[str] = Field(default_factory=list)

class FileConfig_Mods(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    serverMods: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)
    baseMods: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)
    clientMods: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)
    maps: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)

    missionMods: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)

    extraServer: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)
    extraBase: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)
    extraClient: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)
    extraMaps: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)
    extraMission: Optional[List[FileConfig_ModEntry]] = Field(default_factory=list)

    minus_mods: Optional[List[FileConfig_ModEntry]] = Field(
        default_factory=list,
        alias="minus-mods",
    )


class FileConfig_Dlcs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    contact: bool = False
    csla_iron_curtain: bool = Field(
        default=False,
        validation_alias=AliasChoices("csla-iron-curtain", "csla_iron_curtain"),
        serialization_alias="csla-iron-curtain",
    )
    global_mobilization: bool = Field(
        default=False,
        validation_alias=AliasChoices("global-mobilization", "global_mobilization"),
        serialization_alias="global-mobilization",
    )
    sog_prairie_fire: bool = Field(
        default=False,
        validation_alias=AliasChoices("s.o.g-prairie-fire", "s.o.g_prairie_fire", "sog-prairie-fire", "sog_prairie_fire"),
        serialization_alias="s.o.g-prairie-fire",
    )
    western_sahara: bool = Field(
        default=False,
        validation_alias=AliasChoices("western-sahara", "western_sahara"),
        serialization_alias="western-sahara",
    )
    spearhead_1944: bool = Field(
        default=False,
        validation_alias=AliasChoices("spearhead-1944", "spearhead_1944"),
        serialization_alias="spearhead-1944",
    )
    reaction_forces: bool = Field(
        default=False,
        validation_alias=AliasChoices("reaction-forces", "reaction_forces"),
        serialization_alias="reaction-forces",
    )
    expeditionary_forces: bool = Field(
        default=False,
        validation_alias=AliasChoices("expeditionary-forces", "expeditionary_forces"),
        serialization_alias="expeditionary-forces",
    )


class FileConfig_Mission(BaseModel):
    name: str
    autoStart: bool = False
    difficulty: Optional[str] = None


class FileConfig_Defaults(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    maxPlayers: int = 40
    hostname: str = "Arma 3 Server"
    serverPassword: str = ""
    adminPassword: str = ""
    serverCommandPassword: str = ""
    port: int = 2302
    admins: List[FileConfig_Admin] = Field(default_factory=list)

    autoInit: bool = False
    bandwidthAlg: int = 2
    filePatching: bool = False
    limitFPS: int = 60
    enableHT: bool = True
    useOCAP: bool = False
    numHeadless: int = 0

    params: List[str] = Field(default_factory=list)
    world: str = "empty"
    difficulty: str = "Custom"
    missions: List[FileConfig_Mission] = Field(default_factory=list)

    dlcs: FileConfig_Dlcs = Field(default_factory=FileConfig_Dlcs)
    mods: FileConfig_Mods = Field(default_factory=FileConfig_Mods)
    customMods: FileConfig_CustomMods = Field(default_factory=FileConfig_CustomMods)


class FileConfig_Override(BaseModel):
    description: Optional[str] = None
    maxPlayers: Optional[int] = None
    hostname: Optional[str] = None
    serverPassword: Optional[str] = None
    adminPassword: Optional[str] = None
    serverCommandPassword: Optional[str] = None
    port: Optional[int] = None
    admins: Optional[List[FileConfig_Admin]] = None

    autoInit: Optional[bool] = None
    bandwidthAlg: Optional[int] = None
    filePatching: Optional[bool] = None
    limitFPS: Optional[int] = None
    enableHT: Optional[bool] = None
    useOCAP: Optional[bool] = None
    numHeadless: Optional[int] = None
    world: Optional[str] = None
    difficulty: Optional[str] = None

    dlcs: Optional[FileConfig_Dlcs] = None
    mods: Optional[FileConfig_Mods] = None
    customMods: Optional[FileConfig_CustomMods] = None

    params: Optional[Dict[str, Any] | List[str]] = None
    missions: Optional[List[FileConfig_Mission]] = None


class FileConfig_Root(BaseModel):
    config_name: str = Field(validation_alias=AliasChoices("config-name", "config_name"))
    defaults: FileConfig_Defaults
    configs: Dict[str, FileConfig_Override]
