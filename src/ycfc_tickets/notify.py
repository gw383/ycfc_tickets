"""Phone push notifications via ntfy (https://ntfy.sh).

Each alert is a proper rich notification: a headline, a short second line, the club
crest as its icon, the article or fixture image, and a button that opens the right page.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass

from ycfc_tickets.config import Settings
from ycfc_tickets.models import Article, Fixture

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    title: str
    body: str
    url: str  # opened when the notification is tapped
    button: str = "Open"  # label of the action button
    image: str | None = None
    tag: str = "soccer"  # ntfy turns this into an emoji in front of the title
    priority: int = 3  # 1 (quiet) to 5 (urgent); 3 is a normal notification


class NtfyNotifier:
    """Send notifications to everyone subscribed to an ntfy topic.

    ntfy is free and needs no account: the app on your phone subscribes to a topic
    name, and anything published to that topic pops up as a notification.
    """

    def __init__(
        self,
        topic: str,
        server: str = "https://ntfy.sh",
        token: str | None = None,
        icon: str | None = None,
    ):
        if not server.startswith(("https://", "http://")):
            raise ValueError(f"NTFY_SERVER must be an http(s) URL, got {server!r}")
        self.topic, self.server, self.token, self.icon = topic, server.rstrip("/"), token, icon

    def payload(self, alert: Alert) -> dict[str, object]:
        payload: dict[str, object] = {
            "topic": self.topic,
            "title": alert.title,
            "message": alert.body,
            "tags": [alert.tag],
            "priority": alert.priority,
            "click": alert.url,
            "actions": [{"action": "view", "label": alert.button, "url": alert.url}],
        }
        if alert.image:
            payload["attach"] = alert.image
        if self.icon:
            payload["icon"] = self.icon
        return payload

    def send(self, alert: Alert) -> None:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        # Publishing as JSON (rather than HTTP headers) keeps emoji and accents intact.
        req = urllib.request.Request(  # noqa: S310 - scheme checked in __init__
            self.server,
            data=json.dumps(self.payload(alert)).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            resp.read()


def build_notifier(settings: Settings) -> NtfyNotifier | None:
    """Return the notifier, or None if NTFY_TOPIC isn't set."""
    if not settings.ntfy_topic:
        return None
    return NtfyNotifier(
        settings.ntfy_topic, settings.ntfy_server, settings.ntfy_token, settings.ntfy_icon
    )


def tidy_date(text: str) -> str:
    """'Saturday 24th October - Kick Off 3PM' -> 'Saturday 24th October · Kick-off 3pm'."""
    text = re.sub(r"\s+[-–|]\s+", " · ", " ".join(text.split()))
    text = re.sub(r"kick[\s-]*off", "Kick-off", text, flags=re.IGNORECASE)
    return re.sub(r"(\d)\s*([AaPp][Mm])\b", lambda m: m.group(1) + m.group(2).lower(), text)


def ticket_alert(fixture: Fixture, settings: Settings) -> Alert:
    lines = [tidy_date(fixture.date_text), fixture.category]
    return Alert(
        title=f"Tickets on sale: {fixture.name}",
        body="\n".join(line for line in lines if line) or "Home tickets are now available.",
        url=settings.tickets_url,
        button="Buy tickets",
        image=fixture.image_url,
        tag="ticket",
        priority=4,  # worth a buzz: tickets can sell out
    )


def news_alert(article: Article) -> Alert:
    details = [article.category or "Club news"]
    if article.published:
        details.append(f"{article.published:%a} {article.published.day} {article.published:%b}")
    return Alert(
        title=article.title,
        body=" · ".join(details),
        url=article.url,
        button="Read article",
        image=article.image_url,
        tag="newspaper",
        priority=3,
    )


def send(notifier: NtfyNotifier, alert: Alert) -> bool:
    """Send the alert, logging (not raising) on failure. Returns True if it was delivered."""
    try:
        notifier.send(alert)
    except Exception:  # noqa: BLE001 - network errors etc.; caller retries next run
        log.exception("Notification failed: %s", alert.title)
        return False
    log.info("Notified: %s", alert.title)
    return True
