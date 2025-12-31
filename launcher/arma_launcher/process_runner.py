from __future__ import annotations
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from .logging_setup import get_logger

log = get_logger("arma.launcher.proc")

@dataclass
class ProcessHandle:
    name: str
    proc: subprocess.Popen

def _open_log_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return open(path, "a", encoding="utf-8", buffering=1)

class ProcessRunner:
    def __init__(self):
        self.handles: List[ProcessHandle] = []

    def start(self, name: str, cmd: List[str], *, cwd: Optional[Path] = None, log_file: Optional[Path] = None,
              env: Optional[dict] = None) -> ProcessHandle:
        log.info("Starting %s: %s", name, " ".join(cmd))
        stdout = stderr = None
        if log_file:
            fh = _open_log_file(log_file)
            stdout = fh
            stderr = subprocess.STDOUT

        proc = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, stdout=stdout, stderr=stderr, env=env)
        h = ProcessHandle(name=name, proc=proc)
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

    def status(self) -> dict:
        return {h.name: {"pid": h.proc.pid, "returncode": h.proc.poll()} for h in self.handles}
