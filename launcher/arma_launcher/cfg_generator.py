from __future__ import annotations
from pathlib import Path
from .models import MergedConfig
from .logging_setup import get_logger

log = get_logger("arma.launcher.cfg")

def generate_server_cfg(cfg: MergedConfig, out_path: Path) -> None:
    s = cfg.server
    lines = [
        f'hostname = "{s.hostname}";',
        f'password = "{s.password}";',
        f'passwordAdmin = "{s.password_admin}";',
        f'maxPlayers = {s.max_players};',
        f'verifySignatures = {s.verify_signatures};',
        f'BattlEye = {1 if s.battleye else 0};',
    ]
    if s.motd:
        motd = ", ".join([f'"{m}"' for m in s.motd])
        lines.append(f"motd[] = {{ {motd} }};")
        lines.append(f"motdInterval = {s.motd_interval};")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Generated server cfg: %s", out_path)
