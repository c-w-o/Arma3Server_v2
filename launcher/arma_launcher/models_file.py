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
    serverMods: List[FileConfig_ModEntry] = Field(default_factory=list)
    baseMods: List[FileConfig_ModEntry] = Field(default_factory=list)
    clientMods: List[FileConfig_ModEntry] = Field(default_factory=list)
    maps: List[FileConfig_ModEntry] = Field(default_factory=list)

    missionMods: List[FileConfig_ModEntry] = Field(default_factory=list)

    extraServer: List[FileConfig_ModEntry] = Field(default_factory=list)
    extraBase: List[FileConfig_ModEntry] = Field(default_factory=list)
    extraClient: List[FileConfig_ModEntry] = Field(default_factory=list)
    extraMaps: List[FileConfig_ModEntry] = Field(default_factory=list)
    extraMission: List[FileConfig_ModEntry] = Field(default_factory=list)

    minus_mods: List[FileConfig_ModEntry] = Field(
        default_factory=list,
        alias="minus-mods",
    )


class FileConfig_Dlcs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    contact: bool = False
    csla_iron_curtain: bool = Field(default=False, alias="csla-iron-curtain")
    global_mobilization: bool = Field(default=False, alias="global-mobilization")
    sog_prairie_fire: bool = Field(default=False, alias="s.o.g-prairie-fire")
    western_sahara: bool = Field(default=False, alias="western-sahara")
    spearhead_1944: bool = Field(default=False, alias="spearhead-1944")
    reaction_forces: bool = Field(default=False, alias="reaction-forces")
    expeditionary_forces: bool = Field(default=False, alias="expeditionary-forces")


class FileConfig_Mission(BaseModel):
    name: str
    autoStart: bool = False


class FileConfig_Defaults(BaseModel):
    maxPlayers: int
    hostname: str
    serverPassword: str = ""
    adminPassword: str
    serverCommandPassword: str
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
    useOCAP: Optional[bool] = None
    numHeadless: Optional[int] = None
    hostname: Optional[str] = None
    serverPassword: Optional[str] = None
    dlcs: Optional[FileConfig_Dlcs] = None
    mods: Optional[FileConfig_Mods] = None
    customMods: Optional[FileConfig_CustomMods] = None

    params: Optional[Dict[str, Any]] = None
    missions: Optional[List[FileConfig_Mission]] = None


class FileConfig_Root(BaseModel):
    config_name: str = Field(validation_alias=AliasChoices("config-name", "config_name"))
    defaults: FileConfig_Defaults
    configs: Dict[str, FileConfig_Override]
