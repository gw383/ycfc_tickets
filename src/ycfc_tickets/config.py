"""Settings, read from environment variables (and a local .env file if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SITE_URL = "https://www.yorkcityfootballclub.co.uk"
DEFAULT_URL = f"{SITE_URL}/tickets-and-hospitality/match-tickets/home-tickets"
DEFAULT_NEWS_API = "https://news.cms.web.gc.yorkcityfcservices.co.uk/v2/search"
# Club crest from the website header, shown as the notification's icon (Android only).
DEFAULT_ICON = (
    "https://images.gc.yorkcityfcservices.co.uk/fit-in/350x350/"
    "73853ee0-6bde-11f1-ab07-af1944e4b302.png"
)
DEFAULT_EXCLUDE = ("parking", "hospitality", "season ticket", "membership", "voucher")
TICKET_SOURCES = ("auto", "api", "browser")


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _path(value: str | None) -> Path | None:
    return Path(value).expanduser() if value and value.strip() else None


def _csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    site_url: str = SITE_URL

    # --- Tickets ---
    tickets_enabled: bool = True
    tickets_url: str = DEFAULT_URL
    home_team: str = "York City"
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE
    tickets_source: str = "auto"  # auto = JSON feed, falling back to a browser
    ft_key: str = "ft64f07c7267b9e"  # the club's Future Ticketing widget id
    ft_api_version: str = "v13.0.0"

    # --- News ---
    news_enabled: bool = True
    news_api_url: str = DEFAULT_NEWS_API
    news_categories: tuple[str, ...] = ()  # empty = every category
    news_page_size: int = 15
    news_max_alerts: int = 5  # most news notifications to send in one run

    # --- Notifications (ntfy.sh) ---
    ntfy_topic: str | None = None
    ntfy_server: str = "https://ntfy.sh"
    ntfy_token: str | None = None
    ntfy_icon: str | None = DEFAULT_ICON

    # --- Files ---
    state_file: Path = Path("data/state.json")
    log_file: Path | None = Path("logs/ycfc_tickets.log")

    # --- Browser fallback only ---
    headless: bool = True
    browser_profile: Path | None = None
    page_timeout_ms: int = 30_000

    @classmethod
    def from_env(cls, env_file: str | os.PathLike[str] | None = ".env") -> Settings:
        if env_file:
            load_dotenv(env_file, override=False)
        env = os.environ.get
        log_file = env("LOG_FILE")
        icon = env("NTFY_ICON")
        source = (env("TICKETS_SOURCE") or "auto").strip().lower()
        if source not in TICKET_SOURCES:
            raise ValueError(f"TICKETS_SOURCE must be one of {TICKET_SOURCES}, got {source!r}")
        return cls(
            site_url=(env("SITE_URL") or SITE_URL).rstrip("/"),
            tickets_enabled=_bool(env("TICKETS_ENABLED"), True),
            tickets_url=env("TICKETS_URL") or DEFAULT_URL,
            home_team=env("HOME_TEAM") or "York City",
            exclude_keywords=_csv(env("EXCLUDE_KEYWORDS"), DEFAULT_EXCLUDE),
            tickets_source=source,
            ft_key=env("FT_KEY") or "ft64f07c7267b9e",
            ft_api_version=env("FT_API_VERSION") or "v13.0.0",
            news_enabled=_bool(env("NEWS_ENABLED"), True),
            news_api_url=env("NEWS_API_URL") or DEFAULT_NEWS_API,
            news_categories=_csv(env("NEWS_CATEGORIES"), ()),
            news_page_size=int(env("NEWS_PAGE_SIZE") or 15),
            news_max_alerts=int(env("NEWS_MAX_ALERTS") or 5),
            ntfy_topic=env("NTFY_TOPIC") or None,
            ntfy_server=(env("NTFY_SERVER") or "https://ntfy.sh").rstrip("/"),
            ntfy_token=env("NTFY_TOKEN") or None,
            ntfy_icon=DEFAULT_ICON if icon is None else (icon.strip() or None),
            state_file=_path(env("STATE_FILE")) or Path("data/state.json"),
            log_file=Path("logs/ycfc_tickets.log") if log_file is None else _path(log_file),
            headless=_bool(env("HEADLESS"), True),
            browser_profile=_path(env("BROWSER_PROFILE")),
            page_timeout_ms=int(env("PAGE_TIMEOUT_MS") or 30_000),
        )
