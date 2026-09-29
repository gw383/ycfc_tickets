"""Remember which fixtures have already been alerted on."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_VERSION = 1
FORGET_AFTER = timedelta(days=180)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@dataclass
class FixtureState:
    """Fixtures seen so far, keyed by title, with first/last seen timestamps.

    Seen fixtures are kept (not overwritten each run), so a flaky page load that
    briefly hides a fixture can't cause a duplicate alert when it reappears.
    """

    fixtures: dict[str, dict[str, str]] = field(default_factory=dict)
    is_new_file: bool = False

    @classmethod
    def load(cls, path: Path) -> FixtureState:
        if not path.exists():
            return cls(is_new_file=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(fixtures=dict(data.get("fixtures", {})))

    def unseen(self, current: list[str]) -> list[str]:
        return [f for f in current if f not in self.fixtures]

    def update(self, current: list[str], now: datetime | None = None) -> None:
        now = now or _now()
        stamp = now.isoformat()
        for title in current:
            entry = self.fixtures.setdefault(title, {"first_seen": stamp})
            entry["last_seen"] = stamp
        cutoff = now - FORGET_AFTER
        self.fixtures = {
            title: entry
            for title, entry in self.fixtures.items()
            if datetime.fromisoformat(entry["last_seen"]) >= cutoff
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": STATE_VERSION, "fixtures": self.fixtures}
        # Write to a temp file then swap it in, so a crash never leaves a half-written file.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
