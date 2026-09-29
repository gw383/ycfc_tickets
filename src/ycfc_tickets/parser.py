"""Turn the text of the tickets page into a clean list of fixtures."""

from __future__ import annotations

import re
from collections.abc import Iterable


def _pattern(home_team: str) -> re.Pattern[str]:
    # Matches "York City v Northampton Town", "York City vs. Barnet", "York City V Barrow"
    return re.compile(
        rf"^\s*{re.escape(home_team)}\s+(?:v|vs)\.?\s+(?P<opponent>.+?)\s*$",
        re.IGNORECASE,
    )


def parse_fixtures(
    text: str,
    home_team: str = "York City",
    exclude_keywords: Iterable[str] = (),
) -> list[str]:
    """Return unique fixture titles (in page order) found in ``text``.

    Add-on products such as "York City v Accrington Stanley: Parking" are skipped:
    anything after a colon, or containing an excluded keyword, is not a fixture.
    """
    pattern = _pattern(home_team)
    excluded = [k.lower() for k in exclude_keywords]
    fixtures: dict[str, None] = {}

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())  # collapse odd whitespace / nbsp
        match = pattern.match(line)
        if not match:
            continue
        opponent = match.group("opponent")
        if ":" in opponent or any(k in line.lower() for k in excluded):
            continue
        fixtures[f"{home_team} v {opponent}"] = None

    return list(fixtures)
