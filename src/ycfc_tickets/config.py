"""Settings, read from environment variables (and a local .env file if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_URL = (
    "https://www.yorkcityfootballclub.co.uk/tickets-and-hospitality/match-tickets/home-tickets"
)
DEFAULT_EXCLUDE = ("parking", "hospitality", "season ticket", "membership", "voucher")


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
    tickets_url: str = DEFAULT_URL
    home_team: str = "York City"
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE

    state_file: Path = Path("data/seen_fixtures.json")
    log_file: Path | None = Path("logs/ycfc_tickets.log")

    headless: bool = True
    browser_profile: Path | None = None
    page_timeout_ms: int = 30_000

    # ntfy.sh push notifications. Required for alerts.
    ntfy_topic: str | None = None
    ntfy_server: str = "https://ntfy.sh"
    ntfy_token: str | None = None

    @classmethod
    def from_env(cls, env_file: str | os.PathLike[str] | None = ".env") -> Settings:
        if env_file:
            load_dotenv(env_file, override=False)
        env = os.environ.get
        log_file = env("LOG_FILE")
        return cls(
            tickets_url=env("TICKETS_URL") or DEFAULT_URL,
            home_team=env("HOME_TEAM") or "York City",
            exclude_keywords=_csv(env("EXCLUDE_KEYWORDS"), DEFAULT_EXCLUDE),
            state_file=_path(env("STATE_FILE")) or Path("data/seen_fixtures.json"),
            log_file=Path("logs/ycfc_tickets.log") if log_file is None else _path(log_file),
            headless=_bool(env("HEADLESS"), True),
            browser_profile=_path(env("BROWSER_PROFILE")),
            page_timeout_ms=int(env("PAGE_TIMEOUT_MS") or 30_000),
            ntfy_topic=env("NTFY_TOPIC") or None,
            ntfy_server=(env("NTFY_SERVER") or "https://ntfy.sh").rstrip("/"),
            ntfy_token=env("NTFY_TOKEN") or None,
        )
