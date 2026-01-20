from __future__ import annotations
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.requests import Request
from pydantic import BaseModel
from pathlib import Path
import json
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from .config_loader import load_json, merge_defaults_with_override, transform_file_config_to_internal
from .models_file import FileConfig_Root
from .log_reader import list_logs, read_tail, read_from_cursor
from .settings import Settings
from .orchestrator import Orchestrator

class ActionResult(BaseModel):
    ok: bool
    detail: str | None = None
    data: dict | None = None

class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        resp = await super().get_response(path, scope)
        # Dev-friendly: always fetch latest
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp



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
    
    orch = Orchestrator(settings)
    logs_dir = settings.arma_instance / "logs"
    orch.prepare_environment()
    
    # --- Static UI (no build step) ---
    # Layout:
    #   <repo>/launcher/web/app      (our launcher-control UI)
    #   <repo>/launcher/web/ui-kit-0 (vendored ui-kit/0)
    web_root = Path(__file__).resolve().parents[1] / "web"
    app_root = web_root / "app"
    kit_root = web_root / "ui-kit-0"

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

    @app.get("/config")
    def get_config():
        return orch.cfg.model_dump()

    @app.get("/configs")
    def list_configs():
        """List all available configuration variants and their merged mods/DLCs."""
        cfg_path = orch.layout.inst_config / "server.json"
        raw = load_json(cfg_path)

        # Validate schema (same as config_loader.load_config)
        schema_path = Path(__file__).resolve().parents[1] / "server_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            validate(instance=raw, schema=schema)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"config_schema_invalid: {e.message}")

        root = FileConfig_Root.model_validate(raw)

        out = []
        for name, over in (root.configs or {}).items():
            merged = merge_defaults_with_override(root.defaults, over)
            internal = transform_file_config_to_internal(name, merged)

            def _items(xs):
                return [{"id": int(it.id), "name": it.name} for it in (xs or [])]

            out.append({
                "name": name,
                "description": getattr(over, "description", None),
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

        out.sort(key=lambda x: x.get("name") or "")
        return {"ok": True, "active": root.config_name, "configs": out}

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
    return app

    