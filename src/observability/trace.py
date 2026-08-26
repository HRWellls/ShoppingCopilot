from __future__ import annotations

import json
import threading
from pathlib import Path

from src.models import TraceEvent


class TraceRecorder:
    def __init__(self, enabled: bool, path: Path) -> None:
        self.enabled = enabled
        self.path = Path(path)
        self.degraded = False
        self._lock = threading.Lock()

    def record(self, event: TraceEvent) -> bool:
        if not self.enabled or self.degraded:
            return False
        try:
            payload = json.dumps(event.as_dict(), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(payload + "\n")
                    handle.flush()
            return True
        except (OSError, TypeError, ValueError):
            self.degraded = True
            return False
