"""Decide which ticket listings are real fixtures, and read them out of page text."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ycfc_tickets.models import Fixture

_DATE_HINT = re.compile(r"kick|\b(mon|tues|wednes|thurs|fri|satur|sun)day\b", re.IGNORECASE)


def _pattern(home_team: str) -> re.Pattern[str]:
    # Matches "York City v Northampton Town", "York City vs. Barnet", "York City V Barrow"
    return re.compile(
        rf"^\s*{re.escape(home_team)}\s+(?:v|vs)\.?\s+(?P<opponent>.+?)\s*$",
        re.IGNORECASE,
    )


def fixture_name(
    listing: str,
    home_team: str = "York City",
    exclude_keywords: Iterable[str] = (),
    category: str = "",
) -> str | None:
    """Return a tidy fixture name for a listing title, or None if it isn't a fixture.

    Add-on products such as "York City v Accrington Stanley: Parking" are rejected:
    anything after a colon, or containing an excluded keyword, is not a fixture.
    """
    line = " ".join(listing.split())  # collapse odd whitespace / nbsp
    match = _pattern(home_team).match(line)
    if not match:
        return None
    opponent = match.group("opponent")
    haystack = f"{line} {category}".lower()
    if ":" in opponent or any(k.lower() in haystack for k in exclude_keywords):
        return None
    return f"{home_team} v {opponent}"


def parse_fixtures(
    text: str,
    home_team: str = "York City",
    exclude_keywords: Iterable[str] = (),
) -> list[Fixture]:
    """Unique fixtures (in page order) found in the visible text of the ticket widget.

    Used by the browser fallback. The widget prints each title with its date on the
    next line, so that line is kept as the fixture's date when it looks like one.
    """
    lines = [" ".join(raw.split()) for raw in text.splitlines()]
    lines = [line for line in lines if line]
    fixtures: dict[str, Fixture] = {}
    for i, line in enumerate(lines):
        name = fixture_name(line, home_team, exclude_keywords)
        if not name or name in fixtures:
            continue
        following = lines[i + 1] if i + 1 < len(lines) else ""
        fixtures[name] = Fixture(name, following if _DATE_HINT.search(following) else "")
    return list(fixtures.values())
