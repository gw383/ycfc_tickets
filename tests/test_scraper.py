"""End-to-end check of the browser step against a local copy of the page layout.

Skipped automatically if Playwright's Chromium isn't installed.
"""

from pathlib import Path

import pytest

from ycfc_tickets.config import DEFAULT_EXCLUDE, Settings
from ycfc_tickets.parser import parse_fixtures
from ycfc_tickets.scraper import ScrapeError, fetch_page_text

PAGE = (Path(__file__).parent / "fixtures" / "tickets_page.html").resolve()


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(not _chromium_available(), reason="Playwright Chromium not installed"),
]


def test_waits_for_widget_and_reads_fixtures():
    settings = Settings(tickets_url=PAGE.as_uri(), page_timeout_ms=10_000)
    text = fetch_page_text(settings)
    assert parse_fixtures(text, exclude_keywords=DEFAULT_EXCLUDE) == [
        "York City v Northampton Town",
        "York City v Accrington Stanley",
    ]
    assert "For car parking" not in text  # only the widget's text is read


def test_screenshot_option(tmp_path):
    shot = tmp_path / "page.png"
    settings = Settings(tickets_url=PAGE.as_uri(), page_timeout_ms=10_000)
    fetch_page_text(settings, screenshot=shot)
    assert shot.stat().st_size > 0


def test_headless_browser_is_not_turned_away():
    # This page (like some real ticket widgets) won't render for "HeadlessChrome".
    page = PAGE.with_name("tickets_page_blocks_headless.html")
    settings = Settings(tickets_url=page.as_uri(), page_timeout_ms=10_000, headless=True)
    assert "York City v Northampton Town" in fetch_page_text(settings)


def test_widget_that_never_loads_is_an_error_not_no_fixtures():
    page = PAGE.with_name("widget_never_loads.html")
    settings = Settings(tickets_url=page.as_uri(), page_timeout_ms=2_000)
    with pytest.raises(ScrapeError, match="didn't load"):
        fetch_page_text(settings)
