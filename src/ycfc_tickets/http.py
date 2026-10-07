"""Small HTTP helper (standard library only) for the club's JSON feeds."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

# The feeds are the same ones the club website calls from your browser, so we send
# the same kind of headers a browser on that site would.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


class FetchError(RuntimeError):
    """A page or feed could not be fetched or understood."""


def browser_headers(site: str) -> dict[str, str]:
    site = site.rstrip("/")
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-GB,en;q=0.9",
        "Origin": site,
        "Referer": site + "/",
    }


def get_text(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 20,
    attempts: int = 2,
) -> str:
    if not url.startswith(("https://", "http://")):
        raise FetchError(f"Refusing to fetch non-http URL: {url!r}")
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers=headers or {})  # noqa: S310 - scheme checked
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < attempts:
                log.debug("GET %s failed (%s), retrying", url, exc)
                time.sleep(2)
    raise FetchError(f"GET {url} failed: {last}") from last


def get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 20) -> Any:
    text = get_text(url, headers, timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError(f"GET {url} did not return JSON: {text[:120]!r}") from exc
