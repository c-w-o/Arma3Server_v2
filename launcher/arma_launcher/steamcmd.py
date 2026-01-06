from __future__ import annotations
import subprocess
import threading
import shlex
import re
import time
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import codecs
from .settings import Settings
from .steam_credentials import load_credentials
from .logging_setup import get_logger

log = get_logger("arma.launcher.steamcmd")

@dataclass(frozen=True)
class SteamCmdError(RuntimeError):
    kind: str          # e.g. "NOT_FOUND", "ACCESS_DENIED", "FAILED"
    message: str
    last_lines: tuple[str, ...] = ()

    def __str__(self) -> str:
        if self.last_lines:
            tail = " | ".join(self.last_lines[-5:])
            return f"{self.message} (kind={self.kind}) :: {tail}"
        return f"{self.message} (kind={self.kind})"

_RE_NOT_FOUND = re.compile(r"(File Not Found|No subscription|Invalid PublishedFileId)", re.IGNORECASE)
_RE_ACCESS    = re.compile(r"(Access Denied|private|requires purchase)", re.IGNORECASE)
_RE_RATE_LIMIT = re.compile(r"(Rate Limit Exceeded|Too Many Requests|HTTP\s*429)", re.IGNORECASE)

def _pump_bytes(pipe, log_fn, prefix: str, ring: list[str], ring_max: int = 50) -> None:
    """
    SteamCMD prints progress using carriage returns ('\\r') to rewrite the same line.
    readline() won't emit these. We therefore read bytes and split on both '\\r' and '\\n'.
    """
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    buf = ""
    try:
        while True:
            chunk = pipe.read(4096)
            if not chunk:
                break
            text = decoder.decode(chunk)
            buf += text
            parts = []
            start = 0
            for i, ch in enumerate(buf):
                if ch == "\n" or ch == "\r":
                    parts.append(buf[start:i])
                    start = i + 1
            buf = buf[start:]
            for line in parts:
                line = line.strip()
                if line:
                    log_fn("%s%s", prefix, line)
                    ring.append(line)
                    if len(ring) > ring_max:
                        del ring[: len(ring) - ring_max]
    except Exception:
        return

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
            text=False,
            bufsize=0,
        )

        assert proc.stdout is not None
        assert proc.stderr is not None

        ring: list[str] = []
        t_out = threading.Thread(target=_pump_bytes, args=(proc.stdout, log.info, "[steamcmd] ", ring), daemon=True)
        t_err = threading.Thread(target=_pump_bytes, args=(proc.stderr, log.warning, "[steamcmd] ", ring), daemon=True)
         
        t_out.start()
        t_err.start()

        try:
            rc = proc.wait()
        except KeyboardInterrupt:
            # stop steamcmd cleanly so we don't leave it running in the container
            log.warning("SteamCMD interrupted by user, terminating...")
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            raise
        finally:
            t_out.join(timeout=1)
            t_err.join(timeout=1)

        if rc != 0:
            tail = tuple(ring[-10:])
            joined = "\n".join(tail)
            if _RE_NOT_FOUND.search(joined):
                raise SteamCmdError(kind="NOT_FOUND", message="SteamCMD workshop download failed: item not found", last_lines=tail)
            if _RE_ACCESS.search(joined):
                raise SteamCmdError(kind="ACCESS_DENIED", message="SteamCMD workshop download failed: access denied/private", last_lines=tail)
            if _RE_RATE_LIMIT.search(joined):
                raise SteamCmdError(kind="RATE_LIMIT", message="SteamCMD rate limit exceeded", last_lines=tail)
            raise SteamCmdError(kind="FAILED", message=f"SteamCMD failed (rc={rc})", last_lines=tail)

    def _run_with_backoff(self, args: List[str], *, op_name: str, max_attempts: int = 8) -> None:
        """Run steamcmd with retries on rate limiting."""
        base_delay_s = 5.0
        max_delay_s = 600.0  # cap at 10 minutes

        attempt = 0
        while True:
            attempt += 1
            try:
                self._run(args)
                return
            except SteamCmdError as e:
                if e.kind != "RATE_LIMIT" or attempt >= max_attempts:
                    raise

                delay = min(max_delay_s, base_delay_s * (2 ** (attempt - 1)))
                jitter = random.uniform(0.0, min(10.0, delay * 0.1))
                sleep_s = delay + jitter
                log.warning(
                    "SteamCMD rate limit exceeded during %s. Retry %d/%d in %.1fs",
                    op_name, attempt, max_attempts, sleep_s
                )
                time.sleep(sleep_s)


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
        self._run_with_backoff(args, op_name=f"app_update {app_id}", max_attempts=8)

    def workshop_download(self, game_id: int, workshop_id: int, *, validate: bool = False) -> None:
        user, pw = load_credentials(self.settings)
        args = [
            "+login", user, pw,
            "+workshop_download_item", str(game_id), str(workshop_id),
        ]
        if validate:
            args.append("validate")
        args += ["+quit"]
        self._run_with_backoff(args, op_name=f"workshop_download_item {workshop_id}", max_attempts=8)
        
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
