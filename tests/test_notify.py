import json
from datetime import datetime, timezone

import pytest

from ycfc_tickets import notify
from ycfc_tickets.config import DEFAULT_ICON, Settings
from ycfc_tickets.models import Article, Fixture
from ycfc_tickets.notify import (
    Alert,
    NtfyNotifier,
    build_notifier,
    news_alert,
    ticket_alert,
    tidy_date,
)


def test_no_notifier_without_topic():
    assert build_notifier(Settings()) is None


def test_notifier_from_settings():
    n = build_notifier(Settings(ntfy_topic="ycfc-secret", ntfy_server="https://ntfy.example"))
    assert (n.topic, n.server, n.icon) == ("ycfc-secret", "https://ntfy.example", DEFAULT_ICON)


def test_rejects_non_http_server():
    with pytest.raises(ValueError):
        NtfyNotifier("t", "file:///etc")


@pytest.mark.parametrize(
    ("raw", "tidy"),
    [
        ("Saturday 24th October - Kick Off 3PM", "Saturday 24th October · Kick-off 3pm"),
        ("Tuesday 20th October - Kick Off 7:45pm", "Tuesday 20th October · Kick-off 7:45pm"),
        ("Sat 2 Jan  |  kick off 12:30 PM", "Sat 2 Jan · Kick-off 12:30pm"),
        ("", ""),
    ],
)
def test_tidy_date(raw, tidy):
    assert tidy_date(raw) == tidy


def test_ticket_alert():
    fixture = Fixture(
        "York City v Port Vale",
        "Saturday 24th October - Kick Off 3pm",
        "League Fixture",
        "https://img.example/pv.png",
    )
    alert = ticket_alert(fixture, Settings())
    assert alert.title == "Tickets on sale: York City v Port Vale"
    assert alert.body == "Saturday 24th October · Kick-off 3pm\nLeague Fixture"
    assert alert.button == "Buy tickets"
    assert alert.url.endswith("/home-tickets")
    assert alert.image == "https://img.example/pv.png"
    assert alert.priority > news_alert(Article("1", "t", "u")).priority


def test_ticket_alert_without_details():
    assert ticket_alert(Fixture("York City v Barnet"), Settings()).body == (
        "Home tickets are now available."
    )


def test_news_alert():
    article = Article(
        id="1",
        title="⚽ Goal of the Month | September 2026",
        url="https://club.example/news/goal/",
        category="Mens",
        published=datetime(2026, 9, 30, 16, 5, tzinfo=timezone.utc),
        image_url="https://img.example/goal.webp",
    )
    alert = news_alert(article)
    assert alert.title == "⚽ Goal of the Month | September 2026"
    assert alert.body == "Mens · Wed 30 Sep"
    assert (alert.button, alert.url) == ("Read article", "https://club.example/news/goal/")


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b""


def test_publishes_rich_json_notification(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["req"] = req
        return _Resp()

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    alert = Alert(
        title="⚽ Goal – of the Month",
        body="Mens · Wed 30 Sep",
        url="https://club.example/a",
        button="Read article",
        image="https://img.example/a.webp",
        tag="newspaper",
    )
    NtfyNotifier(
        "my-topic", "https://ntfy.sh/", token="tk", icon="https://img.example/crest.png"
    ).send(alert)

    req = captured["req"]
    assert req.full_url == "https://ntfy.sh"  # the topic is in the body, never in the URL
    assert req.get_header("Authorization") == "Bearer tk"
    assert json.loads(req.data.decode("utf-8")) == {
        "topic": "my-topic",
        "title": "⚽ Goal – of the Month",  # emoji and dashes survive
        "message": "Mens · Wed 30 Sep",
        "tags": ["newspaper"],
        "priority": 3,
        "click": "https://club.example/a",
        "actions": [{"action": "view", "label": "Read article", "url": "https://club.example/a"}],
        "attach": "https://img.example/a.webp",
        "icon": "https://img.example/crest.png",
    }


def test_image_and_icon_are_optional():
    payload = NtfyNotifier("t").payload(Alert("a", "b", "https://u"))
    assert "attach" not in payload
    assert "icon" not in payload


def test_send_returns_false_on_network_error(monkeypatch):
    def boom(req, timeout):
        raise OSError("no network")

    monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
    assert notify.send(NtfyNotifier("t"), Alert("t", "b", "https://u")) is False
