"""Phone push notifications via ntfy (https://ntfy.sh)."""

from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass

from ycfc_tickets.config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    title: str
    body: str
    url: str


class NtfyNotifier:
    """Send a push notification to everyone subscribed to an ntfy topic.

    ntfy is free and needs no account: the app on your phone subscribes to a topic
    name, and anything POSTed to https://ntfy.sh/<topic> pops up as a notification.
    """

    def __init__(self, topic: str, server: str = "https://ntfy.sh", token: str | None = None):
        if not server.startswith(("https://", "http://")):
            raise ValueError(f"NTFY_SERVER must be an http(s) URL, got {server!r}")
        self.topic, self.server, self.token = topic, server.rstrip("/"), token

    def send(self, alert: Alert) -> None:
        headers = {
            # HTTP headers must be latin-1; keep the title plain ASCII.
            "Title": alert.title.encode("ascii", "ignore").decode(),
            "Tags": "soccer,ticket",
            "Priority": "high",
            "Click": alert.url,  # tapping the notification opens the tickets page
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(  # noqa: S310 - scheme checked in __init__
            f"{self.server}/{self.topic}",
            data=alert.body.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            resp.read()


def build_notifier(settings: Settings) -> NtfyNotifier | None:
    """Return the notifier, or None if NTFY_TOPIC isn't set."""
    if not settings.ntfy_topic:
        return None
    return NtfyNotifier(settings.ntfy_topic, settings.ntfy_server, settings.ntfy_token)


def fixtures_alert(new_fixtures: list[str], url: str) -> Alert:
    count = len(new_fixtures)
    title = "YCFC: new fixture on sale" if count == 1 else f"YCFC: {count} new fixtures on sale"
    body = "\n".join(f"- {f}" for f in new_fixtures)
    return Alert(title=title, body=body, url=url)


def send(notifier: NtfyNotifier, alert: Alert) -> bool:
    """Send the alert, logging (not raising) on failure. Returns True if it was delivered."""
    try:
        notifier.send(alert)
    except Exception:  # noqa: BLE001 - network errors etc.; caller retries next run
        log.exception("ntfy alert failed")
        return False
    log.info("ntfy alert sent")
    return True
