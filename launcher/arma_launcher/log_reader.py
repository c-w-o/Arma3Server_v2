import base64, json, os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

@dataclass
class LogChunk:
    entries: List[str]
    cursor: str
    truncated: bool

def _encode_cursor(pos: int, size: int) -> str:
    payload = {"pos": pos, "size": size}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

def _decode_cursor(cursor: str) -> Optional[dict]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None

def list_logs(logs_dir: Path) -> list[dict]:
    out = []
    for p in sorted(logs_dir.glob("*.log")):
        st = p.stat()
        out.append({
            "id": p.stem,  # launcher, server, hc-1, ...
            "path": str(p.relative_to(logs_dir.parent)),
            "size_bytes": st.st_size,
            "modified": int(st.st_mtime),
        })
    return out

def read_tail(path: Path, tail_lines: int = 200, max_bytes: int = 256_000) -> LogChunk:
    # simple + safe: read up to max_bytes from end, then split lines
    st = path.stat()
    size = st.st_size
    read_from = max(0, size - max_bytes)
    with path.open("rb") as f:
        f.seek(read_from)
        data = f.read()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    chunk = lines[-tail_lines:] if tail_lines > 0 else lines
    # cursor points to end of file
    return LogChunk(entries=chunk, cursor=_encode_cursor(size, size), truncated=(len(lines) > len(chunk)))

def read_from_cursor(path: Path, cursor: str, max_lines: int = 200, max_bytes: int = 256_000) -> LogChunk:
    st = path.stat()
    size = st.st_size
    decoded = _decode_cursor(cursor) or {"pos": 0, "size": 0}
    pos = int(decoded.get("pos", 0))

    # handle truncate/rotate: if file shrank, start from 0
    if pos > size:
        pos = 0

    with path.open("rb") as f:
        f.seek(pos)
        data = f.read(max_bytes)

    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()

    # If we cut mid-line due to max_bytes, last line might be partial.
    # That's acceptable for viewers; or you can buffer it client-side.
    out_lines = lines[:max_lines]
    truncated = len(lines) > len(out_lines)

    # compute next cursor: move by bytes actually read up to the end of included lines
    # simplest: advance by len(data) if we returned everything we read;
    # if max_lines cut earlier, approximate by re-encoding joined lines.
    if truncated:
        consumed = ("\n".join(out_lines) + "\n").encode("utf-8", errors="replace")
        next_pos = pos + len(consumed)
    else:
        next_pos = min(size, pos + len(data))

    return LogChunk(entries=out_lines, cursor=_encode_cursor(next_pos, size), truncated=truncated)
