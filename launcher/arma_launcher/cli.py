from __future__ import annotations
import argparse
import json
import uvicorn
from .settings import Settings
from .logging_setup import setup_logging
from .orchestrator import Orchestrator
from .api import create_app

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="arma-launcher")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Sync + generate cfg + start server (+ headless clients)")
    run_p.add_argument("--no-start", action="store_true", help="Only sync + generate config; don't start Arma processes")
    run_p.add_argument("--dry-run", action="store_true", help="Plan only; do not touch SteamCMD or filesystem")

    plan_p = sub.add_parser("plan", help="Print a dry-run plan as JSON and exit")

    api_p = sub.add_parser("api", help="Run REST API (FastAPI)")
    api_p.add_argument("--host", default="0.0.0.0")
    api_p.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    settings = Settings()
    setup_logging(settings)

    if args.cmd == "plan":
        orch = Orchestrator(settings)
        orch.prepare_environment()
        plan = orch.plan().to_dict()
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0 if plan.get("ok", True) else 1

    if args.cmd == "run":
        orch = Orchestrator(settings)
        orch.prepare_environment()
        orch.ensure_arma()

        if args.dry_run:
            plan = orch.plan().to_dict()
            # include implied cfg path
            plan["generated_cfg_path"] = str(orch.generate_server_cfg(dry_run=True))
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 0 if plan.get("ok", True) else 1

        orch.ensure_arma()
        orch.sync_content(dry_run=False)
        orch.generate_server_cfg(dry_run=False)
        if args.no_start:
            return 0
        return orch.start_server()

    if args.cmd == "api":
        app = create_app(settings)
        uvicorn.run(app, host=args.host, port=args.port, log_level=settings.log_level.lower())
        return 0

    return 2
