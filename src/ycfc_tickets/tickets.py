"""Find out which home fixtures are on sale.

The club's tickets page is filled in by a Future Ticketing widget. That widget gets its
list of events from a small JSON feed, so we ask the same feed directly: one quick web
request, no browser needed. If the feed ever stops working, we can fall back to loading
the page in a real browser (needs the optional ``browser`` extra).
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlencode

from ycfc_tickets.config import Settings
from ycfc_tickets.http import FetchError, browser_headers, get_json, get_text
from ycfc_tickets.models import Fixture
from ycfc_tickets.parser import fixture_name, parse_fixtures

log = logging.getLogger(__name__)

EMBED_HOST = "https://embed.futureticketing.ie/"
IMAGE_HOST = "https://d3vzzcunewy153.cloudfront.net/"
_VERSION_RE = re.compile(r'gFTversion\s*=\s*"(v[\d.]+)"')


def _events_url(settings: Settings, version: str) -> str:
    query = urlencode({"k": settings.ft_key, "cu": settings.tickets_url})
    return f"{EMBED_HOST}{version}/inc/api/event/?{query}"


def _current_widget_version(settings: Settings) -> str:
    """Read the widget's version out of its loader script (it's part of the feed's URL)."""
    script = get_text(EMBED_HOST + settings.ft_key, browser_headers(settings.site_url))
    match = _VERSION_RE.search(script)
    if not match:
        raise FetchError("Couldn't find the ticket widget's version in its loader script")
    return match.group(1)


def fixtures_from_feed(data: object, settings: Settings) -> list[Fixture]:
    """Turn the widget's event feed into fixtures, dropping parking and other add-ons."""
    if not isinstance(data, dict) or not isinstance(data.get("d"), list):
        raise FetchError("Ticket feed wasn't in the expected format")
    if data.get("e"):
        raise FetchError(f"Ticket feed returned an error code: {data['e']}")

    fixtures: dict[str, Fixture] = {}
    for event in data["d"]:
        if not isinstance(event, dict):
            continue
        category = str(event.get("cecn") or "")
        name = fixture_name(
            str(event.get("ename") or ""),
            settings.home_team,
            settings.exclude_keywords,
            category,
        )
        if not name or name in fixtures:
            continue
        image = str(event.get("eimage") or "")
        fixtures[name] = Fixture(
            name=name,
            date_text=" ".join(str(event.get("eddate") or "").split()),
            category=category,
            image_url=IMAGE_HOST + image.lstrip("/") if image else None,
        )
    return list(fixtures.values())


def fetch_fixtures_api(settings: Settings) -> list[Fixture]:
    headers = browser_headers(settings.site_url)
    try:
        data = get_json(_events_url(settings, settings.ft_api_version), headers)
    except FetchError as first_error:
        # The feed's URL contains the widget version. If the club's ticketing provider
        # has upgraded the widget, look up the new version and try once more.
        version = _current_widget_version(settings)
        if version == settings.ft_api_version:
            raise
        log.warning(
            "Ticket widget is now %s (was %s); set FT_API_VERSION=%s to skip this lookup",
            version,
            settings.ft_api_version,
            version,
        )
        log.debug("First attempt failed with: %s", first_error)
        data = get_json(_events_url(settings, version), headers)
    return fixtures_from_feed(data, settings)


def fetch_fixtures_browser(settings: Settings) -> list[Fixture]:
    try:
        from ycfc_tickets.scraper import ScrapeError, fetch_page_text
    except ImportError as exc:
        raise FetchError(
            'Browser fallback needs Playwright: pip install -e ".[browser]" '
            "then python -m playwright install chromium"
        ) from exc
    try:
        text = fetch_page_text(settings)
    except ScrapeError as exc:
        raise FetchError(str(exc)) from exc
    return parse_fixtures(text, settings.home_team, settings.exclude_keywords)


def fetch_fixtures(settings: Settings) -> list[Fixture]:
    """Fixtures currently listed for sale. Raises FetchError if they can't be read."""
    source = settings.tickets_source
    if source == "browser":
        return fetch_fixtures_browser(settings)
    try:
        return fetch_fixtures_api(settings)
    except FetchError as exc:
        if source == "api":
            raise
        log.warning("Ticket feed failed (%s); trying the browser instead", exc)
        return fetch_fixtures_browser(settings)
