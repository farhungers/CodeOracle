"""Heartbeat — append-only JSONL row each time a scheduled task runs.

Operator uses this to verify Task Scheduler is actually firing. The digest
(future) will flag any > 60 min gap. Kill switch: HEARTBEAT_DISABLED=true.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def beat(path: Path, task: str, extra: dict[str, Any] | None = None) -> None:
    if os.environ.get("HEARTBEAT_DISABLED", "").lower() == "true":
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "task": task,
    }
    if extra:
        row.update(extra)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
