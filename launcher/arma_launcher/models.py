from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, AliasChoices


class ModEntry(BaseModel):
    name: str
    id: int

class ModsBlock(BaseModel):
    serverMods: List[ModEntry] = Field(default_factory=list)
    baseMods: List[ModEntry] = Field(default_factory=list)
    clientMods: List[ModEntry] = Field(default_factory=list)
    maps: List[ModEntry] = Field(default_factory=list)

    extraServer: List[ModEntry] = Field(default_factory=list)
    extraBase: List[ModEntry] = Field(default_factory=list)
    extraClient: List[ModEntry] = Field(default_factory=list)
    extraMaps: List[ModEntry] = Field(default_factory=list)

    minus_mods: List[ModEntry] = Field(
        default_factory=list,
        validation_alias="minus-mods"
    )

class WorkshopItem(BaseModel):
    id: int = Field(..., description="Steam Workshop ID")
    name: Optional[str] = Field(default=None, description="Only for logs, ID is canonical")
    required: bool = Field(default=True, description="If false: ignored when missing")

class WorkshopConfig(BaseModel):
    mods: List[WorkshopItem] = Field(default_factory=list)
    maps: List[WorkshopItem] = Field(default_factory=list)
    servermods: List[WorkshopItem] = Field(default_factory=list)

class SteamConfig(BaseModel):
    force_validate: bool = False

class DlcSpec(BaseModel):
    name: str
    app_id: int
    mount_name: str
    beta_branch: Optional[str] = None
    beta_password: Optional[str] = None

class ServerConfig(BaseModel):
    hostname: str = "Arma 3 Server"
    password: str = ""
    password_admin: str = ""
    max_players: int = 40
    port: int = 2302
    profiles_subdir: str = "profiles"
    missions_dir: str = "mpmissions"
    battleye: bool = True
    verify_signatures: int = 2
    motd: List[str] = Field(default_factory=list)
    motd_interval: int = 5

class RuntimeConfig(BaseModel):
    cpu_count: int = 4
    extra_args: List[str] = Field(default_factory=list)

class HeadlessClientsConfig(BaseModel):
    enabled: bool = False
    count: int = 0
    password: str = ""
    extra_args: List[str] = Field(default_factory=list)


class OcapConfig(BaseModel):
    """
    OCAP is treated as a *custom-built mod* you place into the shared folder:
      ${ARMA_COMMON}/ocap

    We simply link it into the instance mod or servermod folder.

    - If `source_subdir` is empty: source is the ocap folder itself.
    - Otherwise: source is ${ARMA_COMMON}/ocap/<source_subdir>
    """
    enabled: bool = False
    link_to: str = "servermods"   # "mods" or "servermods"
    link_name: str = "ocap"       # symlink name inside instance folder
    source_subdir: str = ""       # optional subfolder under shared ocap

class ActiveConfig(BaseModel):
    steam: SteamConfig = Field(default_factory=SteamConfig)
    dlcs: List[DlcSpec] = Field(default_factory=list)
    workshop: WorkshopConfig = Field(default_factory=WorkshopConfig)
    headless_clients: HeadlessClientsConfig = Field(default_factory=HeadlessClientsConfig)
    ocap: OcapConfig = Field(default_factory=OcapConfig)

class RootConfig(BaseModel):
    config_name: str
    defaults: Dict[str, Any] = Field(default_factory=dict)
    configs: Dict[str, Dict[str, Any]]

    def build_active(self) -> "MergedConfig":
        if self.config_name not in self.configs:
            raise ValueError(f"config_name={self.config_name!r} not found in configs keys={list(self.configs)}")

        merged: Dict[str, Any] = {}
        merged.update(self.defaults or {})
        merged.update(dict(self.configs[self.config_name] or {}))

        server = ServerConfig.model_validate(merged.get("server", self.defaults.get("server", {})))
        runtime = RuntimeConfig.model_validate(merged.get("runtime", self.defaults.get("runtime", {})))
        active_cfg = ActiveConfig.model_validate(merged)

        return MergedConfig(config_name=self.config_name, server=server, runtime=runtime, active=active_cfg)

class MergedConfig(BaseModel):
    config_name: str
    server: ServerConfig
    runtime: RuntimeConfig
    active: ActiveConfig
