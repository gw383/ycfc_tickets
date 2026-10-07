"""Remember what has already been alerted on, so nothing is announced twice."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

STATE_VERSION = 2
MAX_PER_SECTION = 400  # oldest entries beyond this are forgotten


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class State:
    """Things seen so far, grouped into sections ("fixtures", "news").

    Each section maps a key (fixture name, article id) to when it was first seen.
    Entries are kept rather than overwritten each run, so an item that briefly drops
    off the site can't cause a duplicate alert when it reappears. The file only
    changes when something new is seen, which keeps saved-state updates rare.
    """

    sections: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)
    _loaded: str = ""

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        sections = {
            name: dict(entries)
            for name, entries in data.items()
            if name != "version" and isinstance(entries, dict)
        }
        state = cls(sections=sections)
        state._loaded = state._serialise()
        return state

    def is_first_run(self, section: str) -> bool:
        """True if this section has never been recorded (so we baseline instead of alert)."""
        return section not in self.sections

    def unseen(self, section: str, keys: list[str]) -> list[str]:
        seen = self.sections.get(section, {})
        return [k for k in keys if k not in seen]

    def mark_seen(self, section: str, items: dict[str, str]) -> None:
        """Record ``{key: label}`` as seen. Keys already present are left untouched."""
        entries = self.sections.setdefault(section, {})
        stamp = _now()
        for key, label in items.items():
            if key not in entries:
                entries[key] = {"first_seen": stamp, "label": label}
        if len(entries) > MAX_PER_SECTION:
            newest = sorted(entries.items(), key=lambda kv: kv[1].get("first_seen", ""))
            self.sections[section] = dict(newest[-MAX_PER_SECTION:])

    def _serialise(self) -> str:
        payload = {"version": STATE_VERSION, **self.sections}
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    def save(self, path: Path) -> bool:
        """Write the file if anything changed. Returns True if it was written."""
        text = self._serialise()
        if text == self._loaded and path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file then swap it in, so a crash never leaves a half-written file.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
        self._loaded = text
        return True
