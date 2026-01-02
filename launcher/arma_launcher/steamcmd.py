from __future__ import annotations
import subprocess
import threading
import shlex
from pathlib import Path
from typing import List, Optional
from .settings import Settings
from .steam_credentials import load_credentials
from .logging_setup import get_logger

log = get_logger("arma.launcher.steamcmd")


def _pump(pipe, log_fn, prefix: str) -> None:
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            line = line.rstrip("\n")
            if line:
                log_fn("%s%s", prefix, line)
    finally:
        try:
            pipe.close()
        except Exception:
            pass

class SteamCMD:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bin = settings.steamcmd_sh

    def _run(self, args: List[str]) -> None:
        cmd = [str(self.bin)] + args
        log.info("SteamCMD: %s", self._mask_steamcmd(cmd))

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        assert proc.stdout is not None
        assert proc.stderr is not None

        t_out = threading.Thread(target=_pump, args=(proc.stdout, log.info, "[steamcmd] "), daemon=True)
        t_err = threading.Thread(target=_pump, args=(proc.stderr, log.warning, "[steamcmd] "), daemon=True)
        t_out.start()
        t_err.start()

        rc = proc.wait()
        t_out.join(timeout=1)
        t_err.join(timeout=1)

        if rc != 0:
            raise RuntimeError(f"SteamCMD failed (rc={rc}). See launcher.log for details.")

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
        
    def _mask_steamcmd(self, cmd: List[str]) -> str:
        """
        Mask password in: +login <user> <password>
        Keep everything else visible for debugging.
        """
        out = []
        i = 0
        while i < len(cmd):
            tok = cmd[i]
            out.append(tok)

            if tok == "+login":
                # expected: +login user pass
                if i + 1 < len(cmd):
                    out.append(cmd[i + 1])  # user
                    #out.append("**user**")
                if i + 2 < len(cmd):
                    out.append("***pw***")  # password masked
                i += 3
                continue

            i += 1

        # pretty printing with quoting so spaces/special chars are readable
        return " ".join(shlex.quote(x) for x in out)
