"""Command-line entry point: ``python -m ycfc_tickets`` or ``ycfc-tickets``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ycfc_tickets import __version__
from ycfc_tickets.config import Settings
from ycfc_tickets.http import FetchError
from ycfc_tickets.models import Article, Fixture
from ycfc_tickets.news import fetch_news
from ycfc_tickets.notify import Alert, NtfyNotifier, build_notifier, news_alert, send, ticket_alert
from ycfc_tickets.state import State
from ycfc_tickets.tickets import fetch_fixtures

log = logging.getLogger("ycfc_tickets")

_GITHUB_RUN_VARS = ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")

# 1 and 2 are left for Python crashes and bad command-line arguments.
EXIT_OK, EXIT_FETCH_FAILED, EXIT_ALERT_FAILED = 0, 3, 4

# Tell the phone when a feed has failed this many checks in a row (and again when it's back).
FAILURES_BEFORE_WARNING = 3

# (key remembered in the state file, readable label, notification to send)
Item = tuple[str, str, Alert]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ycfc-tickets",
        description="Notify your phone about new York City FC home tickets and club news.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would happen without sending alerts or saving state",
    )
    p.add_argument(
        "--alert-on-first-run",
        action="store_true",
        help="alert for everything on the first run instead of just recording it",
    )
    p.add_argument(
        "--test-alert",
        action="store_true",
        help="send the latest article and fixture to your phone as a test, then exit",
    )
    p.add_argument(
        "--headed", action="store_true", help="show the window if the browser fallback is used"
    )
    p.add_argument("--env-file", default=".env", help="path to .env file (default: .env)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv)


def _setup_logging(log_file: Path | None, verbose: bool) -> None:
    handlers: list[logging.Handler] = []
    if sys.stdout is not None:  # None under pythonw (no console)
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


def _announce(
    section: str,
    items: list[Item],
    state: State,
    notifier: NtfyNotifier | None,
    args: argparse.Namespace,
    max_alerts: int | None = None,
) -> bool:
    """Alert for the items not seen before and remember them. Returns False if an alert failed.

    ``items`` should be in the order the alerts are to be sent.
    """
    labels = {key: label for key, label, _ in items}
    new = set(state.unseen(section, list(labels)))

    if state.is_first_run(section) and not args.alert_on_first_run:
        log.info("%s: first run, recorded %d item(s) as a baseline, no alert", section, len(items))
        state.mark_seen(section, labels)
        return True
    if not new:
        log.info("%s: nothing new", section)
        state.mark_seen(section, labels)
        return True

    to_send = [item for item in items if item[0] in new]
    if max_alerts is not None and len(to_send) > max_alerts:
        log.warning(
            "%s: %d new items, only alerting for the latest %d", section, len(to_send), max_alerts
        )
        to_send = to_send[-max_alerts:]

    if args.dry_run:
        for _, label, _ in to_send:
            log.info("[dry run] %s: would alert for %s", section, label)
        return True

    failed: set[str] = set()
    for key, label, alert in to_send:
        if notifier is None:
            log.error("%s: new item but NTFY_TOPIC is not set: %s", section, label)
            failed.add(key)
        elif not send(notifier, alert):
            failed.add(key)

    # Anything that failed to send is left unseen, so it is tried again on the next run.
    state.mark_seen(section, {k: v for k, v in labels.items() if k not in failed})
    return not failed


def _track_health(
    name: str,
    error: str | None,
    state: State,
    notifier: NtfyNotifier | None,
    settings: Settings,
    dry_run: bool,
) -> None:
    """Send one "it's broken" notice after repeated failures, and one when it recovers.

    Nobody is watching the logs when this runs on a schedule, so without this a
    blocked or changed website would just mean silence.
    """
    if dry_run:
        return
    if error:
        problems = state.sections.setdefault("problems", {})
        entry = problems.setdefault(name, {"count": "0", "label": ""})
        count = int(entry["count"]) + 1
        if count > FAILURES_BEFORE_WARNING:
            return  # already reported; leave the saved state alone until it recovers
        entry["count"], entry["label"] = str(count), error[:200]
        if count == FAILURES_BEFORE_WARNING and notifier:
            body = f"Couldn't read the club's {name} {FAILURES_BEFORE_WARNING} times in a row."
            send(
                notifier,
                Alert(
                    title="YCFC checker needs a look",
                    body=body + " It will keep trying and tell you when it's working again.",
                    url=_run_url(settings),
                    button="See details",
                    tag="warning",
                    priority=2,
                ),
            )
    elif name in state.sections.get("problems", {}):
        entry = state.sections["problems"].pop(name)
        if not state.sections["problems"]:
            del state.sections["problems"]
        was_reported = int(entry.get("count", "0")) >= FAILURES_BEFORE_WARNING
        if was_reported and notifier:
            send(
                notifier,
                Alert(
                    title="YCFC checker is working again",
                    body=f"The club's {name} can be read again.",
                    url=_run_url(settings),
                    button="See details",
                    tag="white_check_mark",
                    priority=2,
                ),
            )


def _run_url(settings: Settings) -> str:
    """Link to this run's log when on GitHub Actions, otherwise the club site."""
    server, repo, run_id = (os.environ.get(k) for k in _GITHUB_RUN_VARS)
    return (
        f"{server}/{repo}/actions/runs/{run_id}"
        if server and repo and run_id
        else settings.site_url
    )


def _ticket_items(fixtures: list[Fixture], settings: Settings) -> list[Item]:
    return [(f.name, f.name, ticket_alert(f, settings)) for f in fixtures]


def _news_items(articles: list[Article]) -> list[Item]:
    # The feed is newest first; send oldest first so the newest ends up on top.
    return [(a.id, a.title, news_alert(a)) for a in reversed(articles)]


def _test_alert(settings: Settings, notifier: NtfyNotifier | None) -> int:
    if notifier is None:
        log.error("NTFY_TOPIC is not set")
        return EXIT_ALERT_FAILED

    # Use the real latest fixture and article so the test looks exactly like a real alert.
    fixture = Fixture("York City v Example Town", "Saturday 1st January - Kick Off 3pm", "Test")
    article = Article(
        id="test",
        title="Test alert from your YCFC checker",
        url=settings.site_url + "/news/",
        category="Test",
        published=datetime.now(timezone.utc),
    )
    try:
        fixture = (fetch_fixtures(settings) or [fixture])[0]
        article = (fetch_news(settings) or [article])[0]
    except FetchError as exc:
        log.warning("Couldn't load live data for the test (%s); sending samples", exc)

    alerts = [ticket_alert(fixture, settings), news_alert(article)]
    delivered = [send(notifier, alert) for alert in alerts]
    return EXIT_OK if all(delivered) else EXIT_ALERT_FAILED


def run(settings: Settings, args: argparse.Namespace) -> int:
    notifier = build_notifier(settings)
    if args.test_alert:
        return _test_alert(settings, notifier)

    state = State.load(settings.state_file)
    fetch_ok = alerts_ok = True

    if settings.tickets_enabled:
        try:
            fixtures = fetch_fixtures(settings)
        except FetchError as exc:
            log.error("Tickets: %s", exc)
            fetch_ok = False
            _track_health("ticket list", str(exc), state, notifier, settings, args.dry_run)
        else:
            _track_health("ticket list", None, state, notifier, settings, args.dry_run)
            log.info("On sale: %s", "; ".join(f.name for f in fixtures) or "nothing right now")
            items = _ticket_items(fixtures, settings)
            alerts_ok &= _announce("fixtures", items, state, notifier, args)

    if settings.news_enabled:
        try:
            articles = fetch_news(settings)
        except FetchError as exc:
            log.error("News: %s", exc)
            fetch_ok = False
            _track_health("news feed", str(exc), state, notifier, settings, args.dry_run)
        else:
            _track_health("news feed", None, state, notifier, settings, args.dry_run)
            log.info("Latest news: %s", articles[0].title if articles else "none found")
            items = _news_items(articles)
            alerts_ok &= _announce("news", items, state, notifier, args, settings.news_max_alerts)

    if args.dry_run:
        log.info("[dry run] State not saved")
    elif state.save(settings.state_file):
        log.info("Saved state to %s", settings.state_file)

    if not fetch_ok:
        return EXIT_FETCH_FAILED
    return EXIT_OK if alerts_ok else EXIT_ALERT_FAILED


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = Settings.from_env(args.env_file)
    if args.headed:
        settings = replace(settings, headless=False)
    _setup_logging(settings.log_file, args.verbose)
    return run(settings, args)


if __name__ == "__main__":
    raise SystemExit(main())
