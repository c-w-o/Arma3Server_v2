from __future__ import annotations
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from pathlib import Path
from .log_reader import list_logs, read_tail, read_from_cursor
from .settings import Settings
from .orchestrator import Orchestrator

class ActionResult(BaseModel):
    ok: bool
    detail: str | None = None
    data: dict | None = None

def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Arma Launcher API", version="0.3.0")
    orch = Orchestrator(settings)
    logs_dir = settings.arma_instance / "logs"
    orch.prepare_environment()
    

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/config")
    def get_config():
        return orch.cfg.model_dump()

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

    