from __future__ import annotations
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.responses import Response, JSONResponse
from starlette.requests import Request
from pydantic import BaseModel, Field
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import shutil
import json
import re
import html as html_module
import uuid
from jsonschema import validate, RefResolver
from jsonschema.exceptions import ValidationError
from .config_loader import load_json, merge_defaults_with_override, transform_file_config_to_internal, save_config_override
from .models_file import FileConfig_Root, FileConfig_Override, FileConfig_Mods, FileConfig_Dlcs
from .log_reader import list_logs, read_tail, read_from_cursor
from .settings import Settings
from .orchestrator import Orchestrator
from .steamcmd import SteamCMD
from .content_manager import ContentManager
from .steam_metadata import ModMetadataResolver, resolve_mod_ids
from .api_variants import register_variants_routes
from .config.file_layout import ConfigLayout

class ActionResult(BaseModel):
    ok: bool
    detail: str | None = None
    data: dict | None = None


class MissionModEntry(BaseModel):
    id: int
    name: str | None = None


class MissionMetaPayload(BaseModel):
    name: str
    file: str | None = None
    configName: str
    description: str | None = None
    requiredMods: List[MissionModEntry] = Field(default_factory=list)
    optionalMods: List[MissionModEntry] = Field(default_factory=list)

class DefaultsUpdatePayload(BaseModel):
    mods: Optional[FileConfig_Mods] = None
    dlcs: Optional[FileConfig_Dlcs] = None

class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        resp = await super().get_response(path, scope)
        # Dev-friendly: always fetch latest
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp


def _format_schema_error(exc: ValidationError) -> str:
    path = "/".join([str(p) for p in exc.absolute_path]) or "(root)"
    return f"{exc.message} at {path}"


def _load_api_schemas():
    """Load JSON schemas from launcher/api_schemas.json."""
    schema_path = Path(__file__).resolve().parents[1] / "api_schemas.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"api_schemas.json not found at {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


# Cache schemas on module load
_api_schemas_cache = None

def _get_api_schemas():
    global _api_schemas_cache
    if _api_schemas_cache is None:
        _api_schemas_cache = _load_api_schemas()
    return _api_schemas_cache


def _validate_schema_payload(payload: dict, schema_key: str, *, status_code: int = 400) -> None:
    """Validate payload against a schema from api_schemas.json."""
    all_schemas = _get_api_schemas()
    
    if schema_key not in all_schemas.get("properties", {}):
        raise HTTPException(status_code=500, detail=f"schema_not_found: {schema_key}")
    
    schema = all_schemas["properties"][schema_key]
    # Provide resolver for $ref support
    resolver = RefResolver.from_schema(all_schemas)
    
    try:
        validate(instance=payload, schema=schema, resolver=resolver)
    except ValidationError as exc:
        raise HTTPException(status_code=status_code, detail=f"{schema_key} validation failed: {_format_schema_error(exc)}")



def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Arma Launcher API", version="0.3.0")
    # Dev-friendly defaults (works fine behind a reverse proxy too)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add validation error handler for better debugging
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        print(f"[Validation Error] {request.method} {request.url.path}")
        print(f"[Validation Error] Details: {json.dumps(exc.errors(), indent=2)}")
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "body": str(exc.body) if hasattr(exc, 'body') else None},
        )
    
    orch = Orchestrator(settings)
    logs_dir = settings.arma_instance / "logs"
    orch.prepare_environment()
    
    # Initialize mod metadata resolver with layout paths
    mod_paths = {
        "mods": orch.layout.mods,
        "servermods": orch.layout.servermods,
        "maps": orch.layout.maps,
        "dlcs": orch.layout.dlcs,
    }
    mod_resolver = ModMetadataResolver(mod_paths)
    
    # --- Static UI (no build step) ---
    # Layout:
    #   <repo>/launcher/web/app      (our launcher-control UI)
    #   <repo>/launcher/web/ui-kit-0 (vendored ui-kit/0)
    web_root = Path(__file__).resolve().parents[1] / "web"
    app_root = web_root / "app"
    kit_root = web_root / "ui-kit-0"

    # Initialize Variants API for new variant-based configuration
    config_layout = ConfigLayout(orch.layout.inst_config)

    # --- Missions metadata ---
    missions_index_path = config_layout.root / "missions.json"

    def _load_missions_index() -> list[dict]:
        if not missions_index_path.exists():
            return []
        try:
            raw = json.loads(missions_index_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(raw, dict):
            raw = raw.get("missions", [])
        if not isinstance(raw, list):
            return []
        return [m for m in raw if isinstance(m, dict)]

    def _save_missions_index(missions: list[dict]) -> None:
        missions_index_path.parent.mkdir(parents=True, exist_ok=True)
        missions_index_path.write_text(
            json.dumps({"missions": missions}, indent=2),
            encoding="utf-8",
        )

    def _compute_file_hash(file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        hasher = sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _compute_config_hash(config_name: str) -> str:
        defaults = orch.store.load_defaults()
        override = orch.store.load_override(config_name)
        merged = orch.merger.merge(defaults, override)
        payload = merged.model_dump(mode="json", by_alias=True, exclude_none=True)
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(blob).hexdigest()

    def _upsert_mission(meta: dict) -> None:
        """Add mission metadata. Each upload is unique - no updates by name."""
        missions = _load_missions_index()
        mission_id = meta.get("id")
        
        # Ensure new mission has an ID
        if not mission_id:
            meta["id"] = str(uuid.uuid4())
        
        missions.append(meta)
        _save_missions_index(missions)
    if app_root.exists():
        app.mount("/app", NoCacheStaticFiles(directory=str(app_root), html=True), name="app")
    if kit_root.exists():
        app.mount("/ui-kit-0", NoCacheStaticFiles(directory=str(kit_root), html=True), name="ui-kit-0")

    @app.get("/", include_in_schema=False)
    def index():
        # Serve the UI by default.
        idx = app_root / "index.html"
        if idx.exists():
            return FileResponse(str(idx))
        return {"ok": True, "detail": "ui_not_installed"}

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/missions")
    def list_missions(config: str | None = Query(default=None)):
        """List uploaded missions and their associated config hash state."""
        missions = _load_missions_index()
        hash_cache: dict[str, Optional[str]] = {}
        enriched: list[dict] = []

        for m in missions:
            entry = dict(m)
            cfg_name = entry.get("configName")
            current_hash = None
            if cfg_name:
                if cfg_name not in hash_cache:
                    try:
                        hash_cache[cfg_name] = _compute_config_hash(cfg_name)
                    except Exception:
                        hash_cache[cfg_name] = None
                current_hash = hash_cache[cfg_name]
                entry["configHashCurrent"] = current_hash
                if entry.get("configHash") and current_hash:
                    entry["configHashMatch"] = entry.get("configHash") == current_hash
                else:
                    entry["configHashMatch"] = None
            enriched.append(entry)

        if config:
            enriched = [m for m in enriched if m.get("configName") == config]

        return {"ok": True, "missions": enriched}

    @app.post("/missions")
    def save_mission_meta(payload: MissionMetaPayload):
        """Create or update mission metadata (without file upload)."""
        try:
            if payload.configName not in orch.store.list_configs():
                raise HTTPException(status_code=404, detail=f"config '{payload.configName}' not found")
            config_hash = _compute_config_hash(payload.configName)
            now = datetime.now(timezone.utc).isoformat()

            entry = payload.model_dump(mode="json")
            entry["configHash"] = config_hash
            entry["uploadedAt"] = entry.get("uploadedAt") or now
            entry["modifiedBy"] = "api"

            _upsert_mission(entry)
            return {"ok": True, "mission": entry}
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error saving mission metadata: {tb}")
            raise HTTPException(status_code=500, detail=f"Error saving mission: {str(e)}")

    @app.post("/missions/upload")
    async def upload_mission(
        file: UploadFile = File(...),
        configName: str = Form(...),
        missionName: str | None = Form(default=None),
        description: str | None = Form(default=None),
    ):
        """Upload a mission file to mpmissions and register its metadata.
        
        Each upload must be unique. If a file with identical content (same hash) 
        already exists, the upload is rejected.
        """
        try:
            if not file.filename:
                raise HTTPException(status_code=400, detail="missing filename")
            if configName not in orch.store.list_configs():
                raise HTTPException(status_code=404, detail=f"config '{configName}' not found")

            dest_dir = orch.layout.inst_mpmissions
            dest_dir.mkdir(parents=True, exist_ok=True)
            safe_name = Path(file.filename).name
            dest_path = dest_dir / safe_name

            # Write file and compute hash
            with dest_path.open("wb") as f:
                shutil.copyfileobj(file.file, f)
            
            file_hash = _compute_file_hash(dest_path)
            
            # Check for duplicate (same file hash)
            existing_missions = _load_missions_index()
            for mission in existing_missions:
                if mission.get("fileHash") == file_hash:
                    # Duplicate found - clean up temp file and return error
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=409,
                        detail=f"Mission '{mission.get('name')}' with identical content already exists (ID: {mission.get('id')})"
                    )

            mission_name = missionName or Path(safe_name).stem
            config_hash = _compute_config_hash(configName)
            now = datetime.now(timezone.utc).isoformat()

            entry = {
                "id": str(uuid.uuid4()),
                "name": mission_name,
                "file": safe_name,
                "fileHash": file_hash,
                "configName": configName,
                "configHash": config_hash,
                "description": description,
                "uploadedAt": now,
                "modifiedBy": "upload",
                "requiredMods": [],
                "optionalMods": [],
            }

            _upsert_mission(entry)
            return {"ok": True, "mission": entry}
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error uploading mission: {tb}")
            raise HTTPException(status_code=500, detail=f"Error uploading mission: {str(e)}")

    @app.get("/configs")
    def list_configs():
        """List all available configuration variants and their merged mods/DLCs."""
        try:
            # Use new multi-file structure
            config_names = orch.store.list_configs()
            active_config = orch.store.get_active_config()
            defaults = orch.store.load_defaults()
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error in /configs: {tb}")
            raise HTTPException(status_code=500, detail=f"Error loading configs: {str(e)}\n{tb}")

        out = []
        for name in config_names:
            override = orch.store.load_override(name)
            merged = orch.merger.merge(defaults, override)
            internal = transform_file_config_to_internal(name, merged)

            def _items(xs):
                return [{"id": int(it.id), "name": it.name} for it in (xs or [])]

            out.append({
                "name": name,
                "description": getattr(override, "description", None),
                "hostname": internal.server.hostname,
                "port": internal.server.port,
                "useOCAP": bool(internal.active.ocap.enabled),
                "numHeadless": int(internal.active.headless_clients.count if internal.active.headless_clients.enabled else 0),
                "dlcs": [{"mount": d.mount_name, "name": d.name, "app_id": d.app_id} for d in (internal.active.dlcs or [])],
                "workshop": {
                    "mods": _items(internal.active.workshop.mods),
                    "maps": _items(internal.active.workshop.maps),
                    "servermods": _items(internal.active.workshop.servermods),
                    "clientmods": _items(internal.active.workshop.clientmods),
                },
                "custom": {
                    "mods": list(internal.active.custom_mods.mods or []),
                    "servermods": list(internal.active.custom_mods.servermods or []),
                },
            })
            print(f"Config {name}: dlcs = {[d.name for d in (internal.active.dlcs or [])]}")

        out.sort(key=lambda x: x.get("name") or "")
        response = {"ok": True, "active": active_config, "configs": out}
        _validate_schema_payload(response, "ConfigsResponse", status_code=500)
        return response

    @app.get("/config/{config_name}")
    def get_config_detail(config_name: str):
        """Get specific configuration with defaults, overrides, and merged view."""
        try:
            # Use new multi-file structure
            if config_name not in orch.store.list_configs():
                raise HTTPException(status_code=404, detail=f"config '{config_name}' not found")
            
            defaults = orch.store.load_defaults()
            override = orch.store.load_override(config_name)
            merged = orch.merger.merge(defaults, override)
            
            def _mod_items(xs):
                return [{"id": int(it.id), "name": it.name} for it in (xs or [])]
            
            def _dlc_items(dlcs_obj):
                """Extract enabled DLC names from DLC boolean object with display names."""
                if not dlcs_obj:
                    print(f"DEBUG: dlcs_obj is None/empty")
                    return []
                items = []
                try:
                    if hasattr(dlcs_obj, 'model_dump'):
                        dlc_dump = dlcs_obj.model_dump()
                    else:
                        dlc_dump = dlcs_obj.__dict__
                    print(f"DEBUG: dlc_dump = {dlc_dump}")
                except Exception as e:
                    print(f"DEBUG: Error getting dlc_dump: {e}")
                    return []
                
                # Map keys to display names (same as in config_loader.py)
                dlc_catalog = {
                    "contact":              "Contact",
                    "csla_iron_curtain":    "CSLA Iron Curtain",
                    "global_mobilization":  "Global Mobilization",
                    "sog_prairie_fire":     "S.O.G Prairie Fire",
                    "western_sahara":       "Western Sahara",
                    "spearhead_1944":       "Spearhead 1944",
                    "reaction_forces":      "Reaction Forces",
                    "expeditionary_forces": "Expeditionary Forces",
                }
                for key, enabled in dlc_dump.items():
                    print(f"DEBUG: key={key}, enabled={enabled}")
                    if enabled:
                        display_name = dlc_catalog.get(key, key)
                        items.append(display_name)
                print(f"DEBUG: final dlc items = {items}")
                return items
            
            response = {
                "ok": True,
                "name": config_name,
                "description": getattr(override, "description", None),
                "defaults": {
                    "mods": {
                        "serverMods": _mod_items(defaults.mods.serverMods),
                        "baseMods": _mod_items(defaults.mods.baseMods),
                        "clientMods": _mod_items(defaults.mods.clientMods),
                        "maps": _mod_items(defaults.mods.maps),
                        "missionMods": _mod_items(defaults.mods.missionMods),
                        "extraServer": _mod_items(defaults.mods.extraServer),
                        "extraBase": _mod_items(defaults.mods.extraBase),
                        "extraClient": _mod_items(defaults.mods.extraClient),
                        "extraMaps": _mod_items(defaults.mods.extraMaps),
                        "extraMission": _mod_items(defaults.mods.extraMission),
                        "minus_mods": _mod_items(defaults.mods.minus_mods),
                    },
                    "dlcs": _dlc_items(defaults.dlcs)
                },
                "overrides": {
                    "mods": {
                        "serverMods": _mod_items(override.mods.serverMods) if override.mods else [],
                        "baseMods": _mod_items(override.mods.baseMods) if override.mods else [],
                        "clientMods": _mod_items(override.mods.clientMods) if override.mods else [],
                        "maps": _mod_items(override.mods.maps) if override.mods else [],
                        "missionMods": _mod_items(override.mods.missionMods) if override.mods else [],
                        "extraServer": _mod_items(override.mods.extraServer) if override.mods else [],
                        "extraBase": _mod_items(override.mods.extraBase) if override.mods else [],
                        "extraClient": _mod_items(override.mods.extraClient) if override.mods else [],
                        "extraMaps": _mod_items(override.mods.extraMaps) if override.mods else [],
                        "extraMission": _mod_items(override.mods.extraMission) if override.mods else [],
                        "minus_mods": _mod_items(override.mods.minus_mods) if override.mods else [],
                    },
                    "dlcs": _dlc_items(override.dlcs) if override.dlcs else []
                },
                "merged": {
                    "mods": {
                        "serverMods": _mod_items(merged.mods.serverMods),
                        "baseMods": _mod_items(merged.mods.baseMods),
                        "clientMods": _mod_items(merged.mods.clientMods),
                        "maps": _mod_items(merged.mods.maps),
                        "missionMods": _mod_items(merged.mods.missionMods),
                        "extraServer": _mod_items(merged.mods.extraServer),
                        "extraBase": _mod_items(merged.mods.extraBase),
                        "extraClient": _mod_items(merged.mods.extraClient),
                        "extraMaps": _mod_items(merged.mods.extraMaps),
                        "extraMission": _mod_items(merged.mods.extraMission),
                        "minus_mods": _mod_items(merged.mods.minus_mods),
                    },
                    "dlcs": _dlc_items(merged.dlcs)
                }
            }
            _validate_schema_payload(response, "ConfigDetailResponse", status_code=500)
            return response
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error in /config/{config_name}: {tb}")
            raise HTTPException(status_code=500, detail=f"Error loading config: {str(e)}\n{tb}")

    @app.post("/config/{config_name}")
    def save_config(config_name: str, override_data: FileConfig_Override):
        """Save a configuration override using multi-file structure."""
        try:
            _validate_schema_payload(
                override_data.model_dump(exclude_none=True),
                "ConfigOverrideRequest",
                status_code=422,
            )
            # Use new multi-file storage
            orch.store.save_override(config_name, override_data, modified_by="api")
            response = ActionResult(ok=True, detail=f"config '{config_name}' saved to multi-file structure")
            _validate_schema_payload(response.model_dump(), "ActionResult", status_code=500)
            return response
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error saving config: {tb}")
            raise HTTPException(status_code=500, detail=f"Error saving config: {str(e)}\n{tb}")

    @app.post("/defaults", response_model=ActionResult)
    def save_defaults_endpoint(payload: DefaultsUpdatePayload):
        """Update the defaults (basis mods/dlcs) using multi-file structure."""
        try:
            print(f"[POST /defaults] Received payload: mods={payload.mods is not None}, dlcs={payload.dlcs is not None}")
            if payload.mods:
                print(f"[POST /defaults] mods keys: {list(payload.mods.__dict__.keys() if hasattr(payload.mods, '__dict__') else [])}")
            _validate_schema_payload(
                payload.model_dump(exclude_none=True),
                "DefaultsUpdateRequest",
                status_code=422,
            )
            # Use new multi-file storage
            orch.store.save_defaults(mods=payload.mods, dlcs=payload.dlcs)
            response = ActionResult(ok=True, detail="defaults saved to multi-file structure")
            _validate_schema_payload(response.model_dump(), "ActionResult", status_code=500)
            return response
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error saving defaults: {tb}")
            raise HTTPException(status_code=500, detail=f"Error saving defaults: {str(e)}\n{tb}")

    @app.get("/config")
    def get_config():
        """Get active/current config."""
        return orch.cfg.model_dump()

    @app.get("/defaults")
    def get_defaults():
        """Return the default configuration from multi-file structure."""
        try:
            # Load defaults from new multi-file structure
            defaults = orch.store.load_defaults()

            def _mod_items(xs):
                return [{"id": int(it.id), "name": it.name} for it in (xs or [])]

            def _dlc_items(dlcs_obj):
                if not dlcs_obj:
                    return []
                try:
                    dlc_dump = dlcs_obj.model_dump() if hasattr(dlcs_obj, 'model_dump') else dlcs_obj.__dict__
                except Exception:
                    return []
                dlc_catalog = {
                    "contact":              "Contact",
                    "csla_iron_curtain":    "CSLA Iron Curtain",
                    "global_mobilization":  "Global Mobilization",
                    "sog_prairie_fire":     "S.O.G Prairie Fire",
                    "western_sahara":       "Western Sahara",
                    "spearhead_1944":       "Spearhead 1944",
                    "reaction_forces":      "Reaction Forces",
                    "expeditionary_forces": "Expeditionary Forces",
                }
                items = []
                for key, enabled in dlc_dump.items():
                    if enabled:
                        items.append(dlc_catalog.get(key, key))
                return items

            # Mods categories from defaults
            defaults_data = {"mods": {}, "dlcs": []}
            defaults_data["mods"] = {
                "serverMods": _mod_items(getattr(defaults.mods, 'serverMods', None) or []),
                "baseMods": _mod_items(getattr(defaults.mods, 'baseMods', None) or []),
                "clientMods": _mod_items(getattr(defaults.mods, 'clientMods', None) or []),
                "maps": _mod_items(getattr(defaults.mods, 'maps', None) or []),
                "missionMods": _mod_items(getattr(defaults.mods, 'missionMods', None) or []),
            }

            # DLCs
            defaults_data["dlcs"] = _dlc_items(defaults.dlcs)

            response = {"ok": True, "defaults": defaults_data}
            _validate_schema_payload(response, "DefaultsGetResponse", status_code=500)
            return response
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error in /defaults: {tb}")
            raise HTTPException(status_code=500, detail=f"Error loading defaults: {str(e)}\n{tb}")

    @app.get("/plan")
    def plan():
        # Always dry-run; no side effects
        p = orch.plan().to_dict()
        p["generated_cfg_path"] = str(orch.generate_server_cfg(dry_run=True))
        return p

    @app.post("/sync", response_model=ActionResult)
    def sync(dry_run: bool = Query(default=False, description="If true: return plan only, do not touch SteamCMD or filesystem")):
        try:
            if dry_run:
                p = orch.plan().to_dict()
                p["generated_cfg_path"] = str(orch.generate_server_cfg(dry_run=True))
                return ActionResult(ok=bool(p.get("ok", True)), detail="dry-run", data=p)

            orch.sync_content(dry_run=False)
            orch.generate_server_cfg(dry_run=False)
            return ActionResult(ok=True, detail="synced")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def _get_internal_config(config_name: str):
        if config_name not in orch.store.list_configs():
            raise HTTPException(status_code=404, detail=f"config '{config_name}' not found")
        defaults = orch.store.load_defaults()
        override = orch.store.load_override(config_name)
        merged = orch.merger.merge(defaults, override)
        return transform_file_config_to_internal(config_name, merged)

    def _collect_workshop_items(cfg):
        items = []
        def add(kind: str, xs):
            for it in (xs or []):
                items.append((kind, it))
        add("mods", cfg.active.workshop.mods)
        add("clientmods", cfg.active.workshop.clientmods)
        add("maps", cfg.active.workshop.maps)
        add("servermods", cfg.active.workshop.servermods)
        return items

    @app.get("/config/{config_name}/workshop/updates")
    def get_workshop_updates(config_name: str):
        try:
            cfg = _get_internal_config(config_name)
            steamcmd = SteamCMD(settings)
            cm = ContentManager(settings, orch.layout, steamcmd)

            items = []
            for kind, item in _collect_workshop_items(cfg):
                wid = int(item.id)
                name = item.name or str(wid)

                dest_root = {"mods": cm.layout.mods, "clientmods": cm.layout.mods, "maps": cm.layout.maps, "servermods": cm.layout.servermods}.get(kind, cm.layout.mods)
                dest = dest_root / str(wid)
                marker = dest / ".modmeta.json"
                local_meta = cm._read_modmeta(marker) or {}
                local_ts = int(local_meta.get("timestamp") or 0)

                up_to_date, remote_ts = cm._is_workshop_item_up_to_date(wid, dest, marker, name)
                status = "unknown"
                up_to_date_flag = None
                if remote_ts is not None:
                    up_to_date_flag = bool(up_to_date)
                    status = "up_to_date" if up_to_date else "outdated"

                items.append({
                    "id": wid,
                    "name": name,
                    "kind": kind,
                    "required": bool(getattr(item, "required", False)),
                    "installed": dest.exists(),
                    "localTimestamp": local_ts or None,
                    "remoteTimestamp": remote_ts,
                    "syncedAt": local_meta.get("synced_at"),
                    "lastChecked": local_meta.get("last_checked"),
                    "status": status,
                    "upToDate": up_to_date_flag,
                })

            items.sort(key=lambda x: (x.get("kind") or "", x.get("name") or "", x.get("id") or 0))
            return {"ok": True, "config": config_name, "items": items}
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error checking workshop updates: {tb}")
            raise HTTPException(status_code=500, detail=f"Error checking updates: {str(e)}")

    @app.post("/config/{config_name}/workshop/updates", response_model=ActionResult)
    def update_workshop_items(config_name: str, payload: dict = Body(...)):
        try:
            cfg = _get_internal_config(config_name)
            items_req = payload.get("items", [])
            validate = bool(payload.get("validate", False))

            if not isinstance(items_req, list) or not items_req:
                raise HTTPException(status_code=400, detail="items must be a non-empty list")

            available = {}
            for kind, item in _collect_workshop_items(cfg):
                key = f"{kind}:{int(item.id)}"
                available[key] = item

            steamcmd = SteamCMD(settings)
            cm = ContentManager(settings, orch.layout, steamcmd)

            updated = []
            skipped = []
            failed = []
            seen = set()

            for entry in items_req:
                if not isinstance(entry, dict):
                    skipped.append({"entry": entry, "reason": "invalid_entry"})
                    continue
                kind = entry.get("kind")
                mod_id = entry.get("id")
                if not kind or mod_id is None:
                    skipped.append({"entry": entry, "reason": "missing_kind_or_id"})
                    continue
                try:
                    mod_id = int(mod_id)
                except Exception:
                    skipped.append({"entry": entry, "reason": "invalid_id"})
                    continue

                key = f"{kind}:{mod_id}"
                if key in seen:
                    continue
                seen.add(key)

                item = available.get(key)
                if not item:
                    skipped.append({"id": mod_id, "kind": kind, "reason": "not_in_config"})
                    continue

                try:
                    result = cm.ensure_workshop_item(kind, item, validate=validate, dry_run=False)
                    if result is None:
                        skipped.append({"id": mod_id, "kind": kind, "reason": "optional_unavailable"})
                    else:
                        updated.append({"id": mod_id, "kind": kind, "changed": bool(result.changed)})
                except Exception as e:
                    failed.append({"id": mod_id, "kind": kind, "error": str(e)})

            ok = len(failed) == 0
            detail = f"Updated {len(updated)} items, skipped {len(skipped)}, failed {len(failed)}"
            return ActionResult(ok=ok, detail=detail, data={
                "config": config_name,
                "updated": updated,
                "skipped": skipped,
                "failed": failed,
            })
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error updating workshop items: {tb}")
            raise HTTPException(status_code=500, detail=f"Error updating mods: {str(e)}")

    @app.get("/status", response_model=ActionResult)
    def status():
        return ActionResult(ok=True, data=orch.status())

    @app.post("/stop", response_model=ActionResult)
    def stop():
        orch.stop()
        return ActionResult(ok=True, detail="stopped")
    
    @app.post("/start", response_model=ActionResult)
    def start():
        try:
            orch.start()
            return ActionResult(ok=True, detail="started")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/restart", response_model=ActionResult)
    def restart():
        try:
            orch.stop()
            orch.start()
            return ActionResult(ok=True, detail="restarted")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/logs")
    def logs():
        return {"ok": True, "logs": list_logs(logs_dir)}

    @app.get("/logs/{log_id}")
    def get_log(
        log_id: str,
        tail: int = Query(default=200, ge=0, le=5000),
        cursor: str | None = None,
        max_lines: int = Query(default=200, ge=1, le=5000),
    ):
        path = (logs_dir / f"{log_id}.log")
        if not path.exists():
            raise HTTPException(status_code=404, detail="log_not_found")

        if cursor:
            chunk = read_from_cursor(path, cursor=cursor, max_lines=max_lines)
        else:
            chunk = read_tail(path, tail_lines=tail)

        return {
            "ok": True,
            "id": log_id,
            "cursor": chunk.cursor,
            "entries": [{"n": i + 1, "line": line} for i, line in enumerate(chunk.entries)],
            "truncated": chunk.truncated,
        }

    @app.post("/resolve-mod-ids")
    def resolve_mod_ids_endpoint(payload: dict = Body(...)):
        """Resolve mod IDs to names via local .modmeta.json or Steam API."""
        try:
            print(f"[DEBUG] resolve-mod-ids called with payload: {payload}")
            _validate_schema_payload(payload, "ResolveModsRequest", status_code=422)
            
            mod_ids = payload.get("modIds", [])
            print(f"[DEBUG] Extracted mod_ids: {mod_ids}")
            if not mod_ids or len(mod_ids) == 0:
                raise HTTPException(status_code=400, detail="modIds is required and must not be empty")
            
            print(f"[DEBUG] Calling resolve_mod_ids with resolver: {mod_resolver}")
            # Run resolution (checks local .modmeta.json first, then Steam API)
            results = resolve_mod_ids(mod_ids, mod_resolver)
            print(f"[DEBUG] Got results: {results}")
            
            response = {
                "ok": True,
                "mods": results
            }
            print(f"[DEBUG] Validating response schema...")
            _validate_schema_payload(response, "ResolveModsResponse", status_code=500)
            print(f"[DEBUG] Response validated, returning")
            return response
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error resolving mod IDs: {tb}")
            raise HTTPException(status_code=500, detail=f"Error resolving mod IDs: {str(e)}")

    # ========================================
    # HTML Preset Import/Export
    # ========================================
    
    def _generate_html_preset(config_name: str, mods: list[dict], preset_name: str) -> str:
        """Generate Arma3 HTML preset from mod list (matching Arma3 Launcher format)."""
        html_lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<html>',
            '  <!--Created by Arma 3 Server Launcher-->',
            '  <head>',
            '    <meta name="arma:Type" content="preset" />',
            f'    <meta name="arma:PresetName" content="{html_module.escape(preset_name)}" />',
            '    <meta name="generator" content="Arma3 Server Launcher" />',
            '    <title>Arma 3</title>',
            '    <link href="https://fonts.googleapis.com/css?family=Roboto" rel="stylesheet" type="text/css" />',
            '    <style>',
            'body {',
            '    margin: 0;',
            '    padding: 0;',
            '    color: #fff;',
            '    background: #000;',
            '}',
            'body, th, td {',
            '    font: 95%/1.3 Roboto, Segoe UI, Tahoma, Arial, Helvetica, sans-serif;',
            '}',
            'td {',
            '    padding: 3px 30px 3px 0;',
            '}',
            'h1 {',
            '    padding: 20px 20px 0 20px;',
            '    color: white;',
            '    font-weight: 200;',
            '    font-family: segoe ui;',
            '    font-size: 3em;',
            '    margin: 0;',
            '}',
            'em {',
            '    font-variant: italic;',
            '    color: silver;',
            '}',
            '.before-list {',
            '    padding: 5px 20px 10px 20px;',
            '}',
            '.mod-list {',
            '    background: #222222;',
            '    padding: 20px;',
            '}',
            '.footer {',
            '    padding: 20px;',
            '    color: gray;',
            '}',
            'a {',
            '    color: #D18F21;',
            '    text-decoration: underline;',
            '}',
            'a:hover {',
            '    color: #F1AF41;',
            '    text-decoration: none;',
            '}',
            '.from-steam {',
            '    color: #449EBD;',
            '}',
            '    </style>',
            '  </head>',
            '  <body>',
            '    <h1>Arma 3 Mods</h1>',
            '    <p class="before-list">',
            '      <em>Config: ' + html_module.escape(config_name) + '</em>',
            '    </p>',
            '    <div class="mod-list">',
            '      <table>',
        ]
        
        for mod in mods:
            # Handle both Pydantic models and dicts
            if isinstance(mod, dict):
                mod_id = mod.get('id')
                mod_name = html_module.escape(mod.get('name', f'Mod {mod_id}'))
            else:
                # Pydantic model
                mod_id = mod.id
                mod_name = html_module.escape(mod.name or f'Mod {mod_id}')
            
            html_lines.append('        <tr data-type="ModContainer">')
            html_lines.append(f'          <td data-type="DisplayName">{mod_name}</td>')
            html_lines.append('          <td>')
            html_lines.append('            <span class="from-steam">Steam</span>')
            html_lines.append('          </td>')
            html_lines.append('          <td>')
            html_lines.append(f'            <a href="https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}" data-type="Link">https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}</a>')
            html_lines.append('          </td>')
            html_lines.append('        </tr>')
        
        html_lines.extend([
            '      </table>',
            '    </div>',
            '    <div class="footer">',
            '      <span>Created by Arma 3 Server Launcher</span>',
            '    </div>',
            '  </body>',
            '</html>',
        ])
        
        return '\n'.join(html_lines)
    
    def _parse_html_preset(html_content: str) -> list[int]:
        """Parse Arma3 HTML preset and extract mod IDs."""
        # Extract all Steam Workshop URLs
        pattern = r'steamcommunity\.com/sharedfiles/filedetails/\?id=(\d+)'
        matches = re.findall(pattern, html_content)
        return [int(mod_id) for mod_id in matches]
    
    @app.get("/config/{config_name}/preset-all.html", response_class=HTMLResponse)
    async def download_preset_all(config_name: str):
        """Download HTML preset with all mods except serverMods."""
        try:
            defaults = orch.store.load_defaults()
            override = orch.store.load_override(config_name)
            merged = orch.merger.merge(defaults, override)
            
            mods_data = merged.mods if merged.mods else FileConfig_Mods()
            
            # Collect all mods except serverMods
            all_mods = []
            for category in ['baseMods', 'clientMods', 'maps', 'missionMods']:
                items = getattr(mods_data, category, None) or []
                if items:
                    all_mods.extend(items)
            
            # Dedupe by ID
            seen_ids = set()
            unique_mods = []
            for mod in all_mods:
                if mod.id not in seen_ids:
                    seen_ids.add(mod.id)
                    unique_mods.append(mod)
            
            html_content = _generate_html_preset(
                config_name,
                unique_mods,
                f"{config_name} - All Mods"
            )
            
            return HTMLResponse(
                content=html_content,
                headers={
                    "Content-Disposition": f'attachment; filename="{config_name}_all.html"'
                }
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Config '{config_name}' not found")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error generating preset: {tb}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/config/{config_name}/preset-base.html", response_class=HTMLResponse)
    async def download_preset_base(config_name: str):
        """Download HTML preset with baseMods and maps only (no serverMods, no clientMods)."""
        try:
            defaults = orch.store.load_defaults()
            override = orch.store.load_override(config_name)
            merged = orch.merger.merge(defaults, override)
            
            mods_data = merged.mods if merged.mods else FileConfig_Mods()
            
            # Collect baseMods and maps
            base_mods = []
            for category in ['baseMods', 'maps']:
                items = getattr(mods_data, category, None) or []
                if items:
                    base_mods.extend(items)
            
            # Dedupe by ID
            seen_ids = set()
            unique_mods = []
            for mod in base_mods:
                if mod.id not in seen_ids:
                    seen_ids.add(mod.id)
                    unique_mods.append(mod)
            
            html_content = _generate_html_preset(
                config_name,
                unique_mods,
                f"{config_name} - Mods & Maps"
            )
            
            return HTMLResponse(
                content=html_content,
                headers={
                    "Content-Disposition": f'attachment; filename="{config_name}_base.html"'
                }
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Config '{config_name}' not found")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error generating preset: {tb}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/config/{config_name}/import-preset")
    async def import_html_preset(config_name: str, file: UploadFile = File(...)):
        """
        Import HTML preset: 
        - Extract baseMods and maps from uploaded HTML
        - Remove disallowed clientMods
        - Return sanitized HTML for download
        """
        try:
            # Read uploaded file
            html_content = (await file.read()).decode('utf-8')
            
            # Parse mod IDs from HTML
            uploaded_mod_ids = _parse_html_preset(html_content)
            
            if not uploaded_mod_ids:
                raise HTTPException(status_code=400, detail="No mod IDs found in uploaded HTML")
            
            # Load current config to get allowed mods
            defaults = orch.store.load_defaults()
            override = orch.store.load_override(config_name)
            merged = orch.merger.merge(defaults, override)
            mods_data = merged.mods if merged.mods else FileConfig_Mods()
            
            # Get IDs of allowed baseMods, maps, and missionMods
            allowed_ids = set()
            for category in ['baseMods', 'maps', 'missionMods']:
                items = getattr(mods_data, category, None) or []
                for mod in items:
                    allowed_ids.add(mod.id)
            
            # Get IDs of clientMods (to be filtered out)
            client_mod_ids = set()
            items = getattr(mods_data, 'clientMods', None) or []
            for mod in items:
                client_mod_ids.add(mod.id)
            
            # Filter: keep only allowed mods, remove clientMods
            filtered_mod_ids = [
                mod_id for mod_id in uploaded_mod_ids 
                if mod_id in allowed_ids and mod_id not in client_mod_ids
            ]
            
            # Resolve names for filtered mods
            resolved_mods = []
            for mod_id in filtered_mod_ids:
                # Find name from config
                name = None
                for category in ['baseMods', 'maps', 'missionMods']:
                    items = getattr(mods_data, category, None) or []
                    for mod in items:
                        if mod.id == mod_id:
                            name = mod.name or f'Mod {mod_id}'
                            break
                    if name:
                        break
                
                resolved_mods.append({'id': mod_id, 'name': name or f'Mod {mod_id}'})
            
            # Generate sanitized HTML
            sanitized_html = _generate_html_preset(
                config_name,
                resolved_mods,
                f"{config_name} - Sanitized"
            )
            
            return {
                "ok": True,
                "detail": f"Processed {len(uploaded_mod_ids)} uploaded mods, kept {len(filtered_mod_ids)} allowed mods",
                "data": {
                    "uploadedCount": len(uploaded_mod_ids),
                    "filteredCount": len(filtered_mod_ids),
                    "removedCount": len(uploaded_mod_ids) - len(filtered_mod_ids),
                    "sanitizedHtml": sanitized_html
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error importing HTML preset: {tb}")
            raise HTTPException(status_code=500, detail=f"Error importing preset: {str(e)}")

    # Register variant configuration API routes
    register_variants_routes(app, settings, config_layout)

    return app

    