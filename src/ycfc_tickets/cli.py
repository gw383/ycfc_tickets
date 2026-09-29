"""Command-line entry point: ``python -m ycfc_tickets`` or ``ycfc-tickets``."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ycfc_tickets import __version__
from ycfc_tickets.config import Settings
from ycfc_tickets.notify import Alert, build_notifier, fixtures_alert, send
from ycfc_tickets.parser import parse_fixtures
from ycfc_tickets.scraper import ScrapeError, fetch_page_text
from ycfc_tickets.state import FixtureState

log = logging.getLogger("ycfc_tickets")

EXIT_OK, EXIT_SCRAPE_FAILED, EXIT_ALERT_FAILED = 0, 1, 2


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ycfc-tickets",
        description="Check the York City FC tickets page and alert on newly listed fixtures.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would happen without sending alerts or saving state",
    )
    p.add_argument("--headed", action="store_true", help="show the browser window")
    p.add_argument(
        "--screenshot",
        type=Path,
        metavar="PNG",
        help="also save a full-page screenshot (for debugging)",
    )
    p.add_argument(
        "--alert-on-first-run",
        action="store_true",
        help="alert for everything on the first run instead of just recording it",
    )
    p.add_argument(
        "--test-alert",
        action="store_true",
        help="send a test notification to your phone and exit",
    )
    p.add_argument("--env-file", default=".env", help="path to .env file (default: .env)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv)


def _setup_logging(log_file: Path | None, verbose: bool) -> None:
    handlers: list[logging.Handler] = []
    if sys.stdout is not None:  # None under pythonw (scheduled task, no console)
        handlers.append(logging.StreamHandler(sys.stdout))
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        )
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


def _fetch_with_retry(settings: Settings, screenshot: Path | None, attempts: int = 2) -> str:
    for attempt in range(1, attempts + 1):
        try:
            return fetch_page_text(settings, screenshot)
        except ScrapeError:
            if attempt == attempts:
                raise
            log.warning("Page load failed (attempt %d/%d), retrying in 10s", attempt, attempts)
            time.sleep(10)
    raise AssertionError("unreachable")


def run(settings: Settings, args: argparse.Namespace) -> int:
    notifier = build_notifier(settings)

    if args.test_alert:
        if notifier is None:
            log.error("NTFY_TOPIC is not set in .env")
            return EXIT_ALERT_FAILED
        alert = Alert(
            "YCFC ticket checker: test alert",
            "If you can read this, alerts are working.",
            settings.tickets_url,
        )
        return EXIT_OK if send(notifier, alert) else EXIT_ALERT_FAILED

    try:
        text = _fetch_with_retry(settings, args.screenshot)
    except ScrapeError as exc:
        log.error("%s", exc)
        return EXIT_SCRAPE_FAILED

    log.debug("Page text:\n%s", text)
    current = parse_fixtures(text, settings.home_team, settings.exclude_keywords)
    if not current:
        log.info("No fixtures on sale right now")
        return EXIT_OK
    log.info("On sale: %s", "; ".join(current))

    state = FixtureState.load(settings.state_file)
    new = state.unseen(current)
    exit_code = EXIT_OK

    if state.is_new_file and not args.alert_on_first_run:
        log.info("First run: recorded %d fixture(s) as a baseline, no alert sent", len(current))
    elif not new:
        log.info("Nothing new")
    elif args.dry_run:
        log.info("[dry run] Would alert for: %s", "; ".join(new))
    else:
        if notifier is None:
            log.error("New fixture(s) but NTFY_TOPIC is not set: %s", "; ".join(new))
            delivered = False
        else:
            delivered = send(notifier, fixtures_alert(new, settings.tickets_url))
        if not delivered:
            # Don't mark them as seen, so we try again on the next run.
            current = [f for f in current if f not in new]
            exit_code = EXIT_ALERT_FAILED

    if args.dry_run:
        log.info("[dry run] State not saved")
    else:
        state.update(current)
        state.save(settings.state_file)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = Settings.from_env(args.env_file)
    if args.headed:
        settings = replace(settings, headless=False)
    _setup_logging(settings.log_file, args.verbose)
    return run(settings, args)


if __name__ == "__main__":
    raise SystemExit(main())
