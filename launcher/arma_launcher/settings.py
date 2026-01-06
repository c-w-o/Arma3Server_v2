from __future__ import annotations
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    arma_root: Path = Field(default=Path("/arma3"), alias="ARMA_ROOT")
    arma_common: Path = Field(default=Path("/var/run/share/arma3/server-common"), alias="ARMA_COMMON")
    arma_instance: Path = Field(default=Path("/var/run/share/arma3/this-server"), alias="ARMA_INSTANCE")
    arma_custom_mods: Path = Field(default=Path("/var/run/share/arma3/this-server/custom-mods"), alias="ARMA_CUSTOM_MODS")
    steamcmd_root: Path = Field(default=Path("/steamcmd"), alias="STEAMCMD_ROOT")
    steam_library_root: Path = Field(default=Path("/root/Steam"), alias="STEAM_LIBRARY_ROOT")
    tmp_dir: Path = Field(default=Path("/tmp"), alias="TMP_DIR")

    arma_binary: Path = Field(default=Path("/arma3/arma3server_x64"), alias="ARMA_BINARY")
    steamcmd_sh: Path = Field(default=Path("/steamcmd/steamcmd.sh"), alias="STEAMCMD_SH")

    steam_user: str = Field(default="", alias="STEAM_USER")
    steam_password: str = Field(default="", alias="STEAM_PASSWORD")
    steam_credentials_json: Path = Field(default=Path("/var/run/share/steam_credentials.json"), alias="STEAM_CREDENTIALS_JSON")

    skip_install: bool = Field(default=False, alias="SKIP_INSTALL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")

    arma_app_id: int = Field(default=233780)
    arma_workshop_game_id: int = Field(default=107410)

    model_config = SettingsConfigDict(extra="ignore")
