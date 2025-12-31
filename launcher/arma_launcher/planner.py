from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

@dataclass
class PlanAction:
    action: str
    target: str
    detail: str
    paths: Dict[str, str]
    will_change: bool
    severity: str = "info"  # info|warn|error

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Plan:
    ok: bool
    actions: List[PlanAction]
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "actions": [a.to_dict() for a in self.actions],
            "notes": list(self.notes),
        }
