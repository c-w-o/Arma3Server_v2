from __future__ import annotations
import subprocess
from pathlib import Path
from typing import List, Optional
from .settings import Settings
from .steam_credentials import load_credentials
from .logging_setup import get_logger

log = get_logger("arma.launcher.steamcmd")

class SteamCMD:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bin = settings.steamcmd_sh

    def _run(self, args: List[str]) -> None:
        cmd = [str(self.bin)] + args
        log.info("SteamCMD: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stdout:
            log.debug("steamcmd stdout: %s", proc.stdout[-4000:])
        if proc.stderr:
            log.debug("steamcmd stderr: %s", proc.stderr[-4000:])
        if proc.returncode != 0:
            raise RuntimeError(f"SteamCMD failed (rc={proc.returncode}). See launcher.log for details.")

    def ensure_app(self, app_id: int, install_dir: Path, *, validate: bool = False,
                   beta_branch: Optional[str] = None, beta_password: Optional[str] = None) -> None:
        user, pw = load_credentials(self.settings)
        args: List[str] = [
            "+force_install_dir", str(install_dir),
            "+login", user, pw,
            "+app_update", str(app_id),
        ]
        if beta_branch:
            args += ["-beta", beta_branch]
            if beta_password:
                args += ["-betapassword", beta_password]
        if validate:
            args.append("validate")
        args += ["+quit"]
        self._run(args)

    def workshop_download(self, game_id: int, workshop_id: int, *, validate: bool = False) -> None:
        user, pw = load_credentials(self.settings)
        args = [
            "+login", user, pw,
            "+workshop_download_item", str(game_id), str(workshop_id),
        ]
        if validate:
            args.append("validate")
        args += ["+quit"]
        self._run(args)
