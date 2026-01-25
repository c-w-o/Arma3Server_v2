from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from .logging_setup import get_logger
from .models import (
    MergedConfig,
    ActiveConfig,
    DlcSpec,
    HeadlessClientsConfig,
    OcapConfig,
    RuntimeConfig,
    ServerConfig,
    SteamConfig,
    WorkshopConfig,
    WorkshopItem,
    CustomModsConfig
)
from .models_file import (
    FileConfig_Root,
    FileConfig_Defaults,
    FileConfig_Override,
    FileConfig_Mods,
    FileConfig_Dlcs,
    FileConfig_ModEntry,
    FileConfig_CustomMods
)

DLC_CATALOG = {
    "contact":              {"name": "Contact",               "app_id": 1021790, "mount_name": "contact"},
    "csla_iron_curtain":    {"name": "CSLA Iron Curtain",     "app_id": 1294440, "beta_branch": "creatordlc", "mount_name": "csla"},
    "global_mobilization":  {"name": "Global Mobilization",   "app_id": 1042220, "beta_branch": "creatordlc", "mount_name": "gm"},
    "sog_prairie_fire":     {"name": "S.O.G Prairie Fire",    "app_id": 1227700, "beta_branch": "creatordlc", "mount_name": "vn"},
    "western_sahara":       {"name": "Western Sahara",        "app_id": 1681170, "beta_branch": "creatordlc", "mount_name": "ws"},
    "spearhead_1944":       {"name": "Spearhead 1944",        "app_id": 1175380, "beta_branch": "creatordlc", "mount_name": "spe"},
    "reaction_forces":      {"name": "Reaction Forces",       "app_id": 2647760, "beta_branch": "creatordlc", "mount_name": "rf"},
    "expeditionary_forces": {"name": "Expeditionary Forces",  "app_id": 2647780, "beta_branch": "creatordlc", "mount_name": "ef"},
 }

from .logging_setup import get_logger
log = get_logger("arma.launcher.config")

def load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config root must be an object")
    return data

def load_config(config_path: Path) -> MergedConfig:
    log.info("Loading config: %s", config_path)
    raw = load_json(config_path)
    
    schema_path = Path(__file__).resolve().parents[1] / "server_schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"server_schema.json not found at {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        validate(instance=raw, schema=schema)
    except ValidationError as e:
        log.error("JSON schema validation failed: %s", e.message)
        raise
    
    root = FileConfig_Root.model_validate(raw)
    
    if root.config_name not in root.configs:
        raise ValueError(f"config-name '{root.config_name}' not found in configs keys={list(root.configs.keys())}")

    merged_defaults = merge_defaults_with_override(root.defaults, root.configs[root.config_name])
    
    merged = transform_file_config_to_internal(root.config_name, merged_defaults)
    log.info("Active config (merged): %s", merged.config_name)
    return merged

def _merge_scalar(base, over):
    return over if over is not None else base


def merge_dlcs(base: FileConfig_Dlcs, over: Optional[FileConfig_Dlcs]) -> FileConfig_Dlcs:
    if over is None:
        log.info("merge_dlcs: over is None, returning base")
        return base
    b = base.model_dump()
    o = over.model_dump(by_alias=True)
    log.info(f"merge_dlcs: base={b}, over={o}")
    b.update(o)  # override wins
    log.info(f"merge_dlcs: merged={b}")
    return FileConfig_Dlcs.model_validate(b)


def merge_missions(base: List[Any], over: Optional[List[Any]]) -> List[Any]:
    if over is None:
        return list(base or [])
    return list(base or []) + list(over or [])


def _dedupe_and_filter(mods: List[FileConfig_ModEntry], minus_ids: Set[int]) -> List[FileConfig_ModEntry]:
    out: List[FileConfig_ModEntry] = []
    seen: Set[int] = set()
    for m in mods:
        if m.id in minus_ids:
            continue
        if m.id in seen:
            continue
        seen.add(m.id)
        out.append(m)
    return out


def merge_mods(base: FileConfig_Mods, over: Optional[FileConfig_Mods]) -> FileConfig_Mods:
    if over is None:
        return base

    minus_ids: Set[int] = {m.id for m in (over.minus_mods or [])}

    merged = FileConfig_Mods(
        serverMods=_dedupe_and_filter( list(base.serverMods or []) + list(over.serverMods or []) + list(over.extraServer or []), minus_ids ),
        baseMods=_dedupe_and_filter( list(base.baseMods or []) + list(over.baseMods or []) + list(over.extraBase or []), minus_ids ),
        clientMods=_dedupe_and_filter( list(base.clientMods or []) + list(over.clientMods or []) + list(over.extraClient or []), minus_ids ),
        maps=_dedupe_and_filter( list(base.maps or []) + list(over.maps or []) + list(over.extraMaps or []), minus_ids ),
        missionMods=_dedupe_and_filter( list(base.missionMods or []) + list(over.missionMods or []) + list(over.extraMission or []), minus_ids ),
        
        extraServer=[],
        extraBase=[],
        extraClient=[],
        extraMaps=[],
        extraMission=[],
        minus_mods=[]
    )
    return merged

def merge_custom_mods(base: FileConfig_CustomMods, over: Optional[FileConfig_CustomMods]) -> FileConfig_CustomMods:
    if over is None:
        return base
    def _dedupe(xs: list[str]) -> list[str]:
        out=[]
        seen=set()
        for x in xs:
            s=str(x).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out
    return FileConfig_CustomMods(
        mods=_dedupe(list(base.mods or []) + list(over.mods or [])),
        serverMods=_dedupe(list(base.serverMods or []) + list(over.serverMods or [])),
    )
def _merge_flag(args: List[str], flag: str, enabled: bool) -> List[str]:
    """Ensure a boolean command-line flag exists (or not) exactly once."""
    args = [a for a in args if a != flag]
    if enabled:
        args.append(flag)
    return args


def _merge_kv(args: List[str], prefix: str, value: Optional[int]) -> List[str]:
    """Ensure a key=value argument exists exactly once.

    Example: prefix="-limitFPS=", value=60 -> "-limitFPS=60".
    If value is None, the argument is removed.
    """
    args = [a for a in args if not str(a).startswith(prefix)]
    if value is not None:
        args.append(f"{prefix}{value}")
    return args


def _apply_structured_start_params(base_args: List[str], merged: FileConfig_Defaults) -> List[str]:
    """Apply structured defaults (autoInit, bandwidthAlg, filePatching, limitFPS, enableHT)
    to the final runtime argument list.

    We treat these fields as canonical and ensure they are reflected in the final arg list,
    without duplicates.
    """
    args = [str(a).strip() for a in (base_args or []) if str(a).strip()]

    # Boolean flags
    args = _merge_flag(args, "-autoInit", bool(merged.autoInit))
    args = _merge_flag(args, "-filePatching", bool(merged.filePatching))
    args = _merge_flag(args, "-enableHT", bool(merged.enableHT))

    # Key/value args
    bw = int(merged.bandwidthAlg) if merged.bandwidthAlg is not None else None
    if bw is not None and bw != 0:
        args = _merge_kv(args, "-bandwidthAlg=", bw)
    else:
        args = _merge_kv(args, "-bandwidthAlg=", None)

    fps = int(merged.limitFPS) if merged.limitFPS is not None else None
    if fps is not None and fps > 0:
        args = _merge_kv(args, "-limitFPS=", fps)
    else:
        args = _merge_kv(args, "-limitFPS=", None)

    # Final stable de-dupe (preserve order)
    out: List[str] = []
    seen: set[str] = set()
    for a in args:
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out

def _filter_hc_args(args: List[str]) -> List[str]:
    """Headless clients should inherit most runtime args, but we strip server-only switches.

    Keep it conservative: remove flags that are clearly server-specific.
    """
    server_only_exact = {
        "-autoInit",
    }
    # If later you add more canonical server-only flags, put them here.

    out: List[str] = []
    for a in (args or []):
        s = str(a).strip()
        if not s:
            continue
        if s in server_only_exact:
            continue
        out.append(s)
    return out



def merge_defaults_with_override(defaults: FileConfig_Defaults, over: FileConfig_Override) -> FileConfig_Defaults:
    merged = defaults.model_copy()
    merged.hostname = _merge_scalar(merged.hostname, over.hostname)
    merged.serverPassword = _merge_scalar(merged.serverPassword, over.serverPassword)
    merged.useOCAP = _merge_scalar(merged.useOCAP, over.useOCAP)
    merged.numHeadless = _merge_scalar(merged.numHeadless, over.numHeadless)

    log.info(f"Merging DLCs: base={defaults.dlcs.model_dump()}, over={over.dlcs.model_dump() if over.dlcs else None}")
    merged.dlcs = merge_dlcs(merged.dlcs, over.dlcs)
    log.info(f"After merge, merged.dlcs={merged.dlcs.model_dump()}")

    merged.mods = merge_mods(merged.mods, over.mods)
    merged.customMods = merge_custom_mods(merged.customMods, over.customMods)
    merged.missions = merge_missions(merged.missions, over.missions)

    extra_args: List[str] = []
    if isinstance(over.params, list):
        extra_args = [str(x) for x in over.params]
    elif isinstance(over.params, dict):
        extra = over.params.get("extra", "")
        if isinstance(extra, str) and extra.strip():
            extra_args = extra.split()

    merged.params = _apply_structured_start_params(list(merged.params or []) + extra_args, merged)
    return merged

def _to_items(entries: List[FileConfig_ModEntry]) -> List[WorkshopItem]:
    return [WorkshopItem(id=int(m.id), name=m.name) for m in entries]


def transform_file_config_to_internal(config_name: str, merged: FileConfig_Defaults) -> MergedConfig:
    # server.cfg basics
    server = ServerConfig(
        hostname=merged.hostname,
        password=merged.serverPassword,
        password_admin=merged.adminPassword,
        max_players=merged.maxPlayers,
        port=merged.port,
        server_command_password=merged.serverCommandPassword,
        admins=[{"name": a.name, "steamid": a.steamid} for a in (merged.admins or [])],
    )
    runtime = RuntimeConfig( cpu_count=4, extra_args=list(merged.params or []) )

    # Workshop mapping: FileConfig_ unterscheidet base/client/mission – runtime braucht:
    # - mods: alles, was als -mod laufen soll (Server + Headless Clients)
    # - servermods: -serverMod (nur Dedicated Server)
    # - clientmods: NUR für Keys (dürfen NICHT geladen werden)
    mods_combined = list(merged.mods.baseMods or []) + list(merged.mods.missionMods or [])
    clientmods_combined = list(merged.mods.clientMods or [])
    workshop = WorkshopConfig(
        mods=_to_items(mods_combined),
        clientmods=_to_items(clientmods_combined),
        maps=_to_items(merged.mods.maps),
        servermods=_to_items(merged.mods.serverMods),
    )

    # DLC boolean-map -> install specs
    dlcs = []
    dlc_dump = merged.dlcs.__dict__
    log.info(f"DLC dump for {config_name}: {dlc_dump}")
    for key, enabled in dlc_dump.items():
        if not enabled:
            continue
        spec = DLC_CATALOG.get(key)
        if not spec:
            log.warning(f"Unknown DLC key: {key}")
            continue
        dlcs.append(DlcSpec(**spec))
    log.info(f"Resolved DLCs for {config_name}: {len(dlcs)} items")

    # OCAP: FileConfig_ useOCAP flag -> V2 ocap config
    ocap = OcapConfig( enabled=bool(merged.useOCAP), link_to="servermods", link_name="ocap", source_subdir="" )
    
    custom_mods = CustomModsConfig( mods=list(merged.customMods.mods or []), servermods=list(merged.customMods.serverMods or []) )

    # Headless clients
    hc = HeadlessClientsConfig( enabled=bool(merged.numHeadless and merged.numHeadless > 0), count=int(merged.numHeadless or 0), password=merged.serverPassword, extra_args=_filter_hc_args(list(merged.params or [])) )
    active = ActiveConfig( steam=SteamConfig(force_validate=False), dlcs=dlcs, workshop=workshop, headless_clients=hc, ocap=ocap, custom_mods=custom_mods )

    return MergedConfig( config_name=config_name, server=server, runtime=runtime, active=active )


def save_config_override(config_path: Path, config_name: str, override: FileConfig_Override) -> None:
    """Save a configuration override to server.json."""
    raw = load_json(config_path)
    root = FileConfig_Root.model_validate(raw)
    
    if config_name not in root.configs:
        raise ValueError(f"config '{config_name}' not found in server.json")
    
    # MERGE with existing override instead of replacing completely
    existing = root.configs[config_name]
    
    # Only update fields that are explicitly set (not None)
    if override.description is not None:
        existing.description = override.description
    if override.useOCAP is not None:
        existing.useOCAP = override.useOCAP
    if override.numHeadless is not None:
        existing.numHeadless = override.numHeadless
    if override.hostname is not None:
        existing.hostname = override.hostname
    if override.serverPassword is not None:
        existing.serverPassword = override.serverPassword
    if override.dlcs is not None:
        existing.dlcs = override.dlcs
    if override.mods is not None:
        existing.mods = override.mods
    if override.customMods is not None:
        existing.customMods = override.customMods
    if override.params is not None:
        existing.params = override.params
    if override.missions is not None:
        existing.missions = override.missions
    
    # Update the override with merged data
    root.configs[config_name] = existing
    
    # Write back to file
    config_path.write_text(
        json.dumps(root.model_dump(by_alias=True, exclude_none=True), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )
    log.info(f"Saved override for config '{config_name}'")