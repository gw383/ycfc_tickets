"""Load the tickets page in a real browser and return its visible text.

The fixture list is injected by the Future Ticketing widget (into ``#ft_container``)
after the page loads, so a plain HTTP request won't see it. Instead of screenshotting
the page and running OCR, we read the rendered text straight from the DOM: faster,
exact, and no Tesseract install needed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from playwright.sync_api import Browser, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from ycfc_tickets.config import Settings

log = logging.getLogger(__name__)

WIDGET_SELECTOR = "#ft_container"
BLOCKED_RESOURCES = {"image", "media", "font"}

# Resolves once the widget contains the home team's name, i.e. fixtures have rendered.
_WAIT_FOR_FIXTURES_JS = """
([selector, needle]) => {
  const el = document.querySelector(selector);
  return !!el && el.innerText.toLowerCase().includes(needle.toLowerCase());
}
"""


class ScrapeError(RuntimeError):
    """The page could not be loaded."""


def _normal_user_agent(browser: Browser) -> str:
    """The browser's own user agent, minus the 'Headless' giveaway."""
    page = browser.new_page()
    try:
        return page.evaluate("navigator.userAgent").replace("HeadlessChrome", "Chrome")
    finally:
        page.close()


def fetch_page_text(settings: Settings, screenshot: Path | None = None) -> str:
    """Return the text of the ticket widget. Raises ScrapeError if it never loads."""
    with sync_playwright() as p:
        if settings.browser_profile:
            context = p.chromium.launch_persistent_context(
                str(settings.browser_profile), headless=settings.headless
            )
            browser = None
        else:
            browser = p.chromium.launch(headless=settings.headless)
            context = browser.new_context(
                # Headless Chromium announces itself as "HeadlessChrome", which some
                # sites (and their ticketing widgets) refuse to serve. Look like normal Chrome.
                user_agent=_normal_user_agent(browser) if settings.headless else None,
                viewport={"width": 1280, "height": 900},
                locale="en-GB",
                timezone_id="Europe/London",
            )

        try:
            if screenshot is None:
                # Skip images/fonts: we only need text, so pages load much faster.
                context.route(
                    "**/*",
                    lambda route: (
                        route.abort()
                        if route.request.resource_type in BLOCKED_RESOURCES
                        else route.continue_()
                    ),
                )

            page = context.new_page()
            page.set_default_timeout(settings.page_timeout_ms)

            log.info("Loading %s", settings.tickets_url)
            try:
                page.goto(settings.tickets_url, wait_until="domcontentloaded")
            except PlaywrightError as exc:
                raise ScrapeError(f"Could not load tickets page: {exc}") from exc

            try:
                page.wait_for_function(
                    _WAIT_FOR_FIXTURES_JS, arg=[WIDGET_SELECTOR, settings.home_team]
                )
            except PlaywrightTimeout:
                # Not fatal: there may simply be no fixtures on sale right now.
                log.warning(
                    "No '%s' fixtures appeared within %d ms",
                    settings.home_team,
                    settings.page_timeout_ms,
                )

            widget = page.locator(WIDGET_SELECTOR)
            text = widget.first.inner_text() if widget.count() else ""

            if screenshot is not None:
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot), full_page=True)
                log.info("Saved screenshot to %s", screenshot)

            if not text.strip():
                # The widget never rendered: we were probably blocked or the page broke.
                # Treat as a failure rather than "nothing on sale", so it shows up in logs.
                raise ScrapeError(
                    "Ticket widget didn't load (blocked or page changed?). "
                    "Try HEADLESS=false, or run with --screenshot debug.png to see the page."
                )

            return text
        finally:
            context.close()
            if browser is not None:
                browser.close()
