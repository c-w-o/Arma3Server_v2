from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .settings import Settings

@dataclass(frozen=True)
class Layout:
    dlcs: Path
    maps: Path
    mods: Path
    ocap: Path
    inst_mods: Path
    inst_servermods: Path
    inst_userconfig: Path
    inst_config: Path
    inst_mpmissions: Path
    inst_logs: Path
    arma_cfg_dir: Path
    arma_keys_dir: Path

def build_layout(settings: Settings) -> Layout:
    common = settings.arma_common
    inst = settings.arma_instance
    return Layout(
        dlcs=common / "dlcs",
        maps=common / "maps",
        mods=common / "mods",
        ocap=common / "ocap",
        inst_mods=inst / "mods",
        inst_servermods=inst / "servermods",
        inst_userconfig=inst / "userconfig",
        inst_config=inst / "config",
        inst_mpmissions=inst / "mpmissions",
        inst_logs=inst / "logs",
        arma_cfg_dir=settings.arma_root / "config",
        arma_keys_dir=settings.arma_root / "keys"
    )

def ensure_dirs(layout: Layout) -> None:
    for p in [
        layout.dlcs, layout.maps, layout.mods, layout.ocap,
        layout.inst_mods, layout.inst_servermods, layout.inst_userconfig,
        layout.inst_config, layout.inst_mpmissions, layout.inst_logs,
        layout.arma_cfg_dir,
        layout.arma_keys_dir
    ]:
        p.mkdir(parents=True, exist_ok=True)
