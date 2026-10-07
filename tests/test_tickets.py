import pytest

from ycfc_tickets import tickets
from ycfc_tickets.config import Settings
from ycfc_tickets.http import FetchError


def test_feed_becomes_fixtures_without_parking(ticket_feed):
    fixtures = tickets.fixtures_from_feed(ticket_feed, Settings())
    assert [f.name for f in fixtures] == [
        "York City v Northampton Town",
        "York City v Accrington Stanley",
        "York City v Port Vale",
    ]
    port_vale = fixtures[-1]
    assert port_vale.date_text == "Saturday 24th October - Kick Off 3pm"
    assert port_vale.category == "League Fixture"
    assert port_vale.image_url == (
        "https://d3vzzcunewy153.cloudfront.net/img/069e8d39-9c6d-4466-ab57-31570e3b27d6/"
        "861051b8c4ce38f679f3bdad7c34eec7.png"
    )


def test_empty_feed_means_nothing_on_sale():
    assert tickets.fixtures_from_feed({"e": "", "d": []}, Settings()) == []


@pytest.mark.parametrize("bad", [None, [], {"x": 1}, {"d": "nope"}, {"e": "ftCode2", "d": []}])
def test_unexpected_feed_is_an_error_not_nothing_on_sale(bad):
    with pytest.raises(FetchError):
        tickets.fixtures_from_feed(bad, Settings())


def test_feed_url_carries_widget_key_and_page(monkeypatch, ticket_feed):
    seen = []

    def fake_get_json(url, headers=None, timeout=20):
        seen.append((url, headers))
        return ticket_feed

    monkeypatch.setattr(tickets, "get_json", fake_get_json)
    assert len(tickets.fetch_fixtures_api(Settings())) == 3
    url, headers = seen[0]
    assert url.startswith(
        "https://embed.futureticketing.ie/v13.0.0/inc/api/event/?k=ft64f07c7267b9e"
    )
    assert "home-tickets" in url
    assert headers["Origin"] == "https://www.yorkcityfootballclub.co.uk"


def test_follows_a_widget_upgrade(monkeypatch, ticket_feed):
    def fake_get_json(url, headers=None, timeout=20):
        if "/v13.0.0/" in url:
            raise FetchError("404")
        assert "/v14.1.0/" in url
        return ticket_feed

    loader = (
        'try{var gFTversion="v14.1.0";var gFTdefMainLocation="https://embed.futureticketing.ie/";'
    )
    monkeypatch.setattr(tickets, "get_json", fake_get_json)
    monkeypatch.setattr(tickets, "get_text", lambda url, headers=None: loader)
    assert len(tickets.fetch_fixtures_api(Settings())) == 3


def test_same_version_failure_is_reported(monkeypatch):
    def boom(url, headers=None, timeout=20):
        raise FetchError("blocked")

    monkeypatch.setattr(tickets, "get_json", boom)
    monkeypatch.setattr(tickets, "get_text", lambda url, headers=None: 'var gFTversion="v13.0.0";')
    with pytest.raises(FetchError, match="blocked"):
        tickets.fetch_fixtures_api(Settings())


def test_auto_falls_back_to_browser(monkeypatch):
    def boom(settings):
        raise FetchError("feed down")

    monkeypatch.setattr(tickets, "fetch_fixtures_api", boom)
    monkeypatch.setattr(tickets, "fetch_fixtures_browser", lambda s: ["from browser"])
    assert tickets.fetch_fixtures(Settings(tickets_source="auto")) == ["from browser"]
    with pytest.raises(FetchError):
        tickets.fetch_fixtures(Settings(tickets_source="api"))
