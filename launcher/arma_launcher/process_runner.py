from __future__ import annotations
import subprocess
import threading
import time
from typing import IO
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from .logging_setup import get_logger

log = get_logger("arma.launcher.proc")

@dataclass
class ProcessHandle:
    name: str
    proc: subprocess.Popen
    _threads: List[threading.Thread] = None
    _log_fh: Optional[IO[str]] = None

def _open_log_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return open(path, "a", encoding="utf-8", buffering=1)

def _parse_arg(cmd: List[str], key: str) -> Optional[str]:
    """
    Supports forms:
      -key=value
      -key value
    """
    prefix = f"-{key}="
    for i, t in enumerate(cmd):
        if isinstance(t, str) and t.startswith(prefix):
            return t[len(prefix):]
        if t == f"-{key}" and i + 1 < len(cmd):
            return cmd[i + 1]
    return None

def _tee_lines(name: str, pipe, log_fh: Optional[IO[str]], *, prefix: str ):
    """
    Read lines from pipe; write to console logger and optionally to file.
    """
    try:
        for line in iter(pipe.readline, ""):
            if line == "":
                break
            line = line.rstrip("\n")
            out = f"[{prefix}] {line}"
            log.info(out)
            if log_fh:
                try:
                    log_fh.write(out + "\n")
                except Exception:
                    pass
    except Exception:
        log.exception("stream tee failed for %s", name)
    finally:
        try:
            pipe.close()
        except Exception:
            pass

def _tail_rpt( name: str, proc: subprocess.Popen, profiles_dir: Path, log_fh: Optional[IO[str]], *, prefix: str, start_timeout_s: float = 60.0 ):
    """
    Tail newest *.rpt in profiles_dir while proc is running.
    """
    try:
        profiles_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    deadline = time.time() + start_timeout_s
    rpt_path: Optional[Path] = None

    # wait for first RPT to appear
    while time.time() < deadline and proc.poll() is None:
        rpts = list(profiles_dir.glob("*.rpt"))
        if rpts:
            rpt_path = max(rpts, key=lambda p: p.stat().st_mtime)
            break
        time.sleep(0.5)

    if rpt_path is None:
        # nothing to tail (or arma never created one)
        return

    try:
        with rpt_path.open("r", encoding="utf-8", errors="replace") as f:
            # read from start (so you also see early init)
            while proc.poll() is None:
                where = f.tell()
                line = f.readline()
                if not line:
                    time.sleep(0.25)
                    f.seek(where)
                    continue
                line = line.rstrip("\n")
                out = f"[{prefix}][RPT] {line}"
                log.info(out)
                if log_fh:
                    try:
                        log_fh.write(out + "\n")
                    except Exception:
                        pass
    except Exception:
        log.exception("RPT tail failed for %s (%s)", name, rpt_path)


class ProcessRunner:
    def __init__(self):
        self.handles: List[ProcessHandle] = []

    def start(self, name: str, cmd: List[str], *, cwd: Optional[Path] = None, log_file: Optional[Path] = None,
              env: Optional[dict] = None) -> ProcessHandle:
        log.info("Starting %s: %s", name, " ".join(cmd))
        # We want BOTH:
        #  - live output in console (docker logs)
        #  - persistent per-process logfile
        fh = _open_log_file(log_file) if log_file else None

        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            bufsize=1,
        )

        threads: List[threading.Thread] = []

        # tee stdout/stderr (merged) to console logger + logfile
        t = threading.Thread(
            target=_tee_lines,
            args=(name, proc.stdout, fh),
            kwargs={"prefix": name},
            daemon=True,
        )
        t.start()
        threads.append(t)

        # tail RPT from profiles dir (Arma writes real logs there)
        profiles = _parse_arg(cmd, "profiles")
        if profiles:
            t_rpt = threading.Thread(
                target=_tail_rpt,
                args=(name, proc, Path(profiles), fh),
                kwargs={"prefix": name},
                daemon=True,
            )
            t_rpt.start()
            threads.append(t_rpt)

        h = ProcessHandle(name=name, proc=proc, _threads=threads, _log_fh=fh)
        self.handles.append(h)
        return h

    def stop_all(self, timeout: float = 10.0) -> None:
        for h in self.handles:
            if h.proc.poll() is None:
                log.info("Stopping %s (pid=%s)", h.name, h.proc.pid)
                h.proc.terminate()
        for h in self.handles:
            if h.proc.poll() is None:
                try:
                    h.proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    log.warning("Killing %s (pid=%s)", h.name, h.proc.pid)
                    h.proc.kill()
        # close file handles
        for h in self.handles:
            if getattr(h, "_log_fh", None):
                try:
                    h._log_fh.close()
                except Exception:
                    pas

    def status(self) -> dict:
        return {h.name: {"pid": h.proc.pid, "returncode": h.proc.poll()} for h in self.handles}
