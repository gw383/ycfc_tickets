from datetime import datetime, timezone

import pytest

from ycfc_tickets import news
from ycfc_tickets.config import Settings
from ycfc_tickets.http import FetchError


def test_feed_becomes_articles(news_feed):
    articles = news.articles_from_feed(news_feed, Settings())
    assert [a.title for a in articles] == [
        "RM English extend partnership.",
        "⚽ Goal of the Month | September 2026",
        "Ticket News | Newport County (A)",
    ]  # the unpublished draft is left out
    first = articles[0]
    assert first.id == "99382ca0-c161-11f1-936c-3171a6c1ebd4"
    assert first.url == (
        "https://www.yorkcityfootballclub.co.uk/news/2026/october/06/rm-english-extend-partnership/"
    )
    assert first.category == "Commercial"
    assert first.published == datetime(2026, 10, 6, 8, 40, 31, tzinfo=timezone.utc)
    assert first.image_url == (
        "https://images.gc.yorkcityfcservices.co.uk/fit-in/1200x675/"
        "822d2060-c161-11f1-9957-e7b7a552be28.webp"
    )
    assert articles[2].image_url is None


def test_category_filter(news_feed):
    settings = Settings(news_categories=("ticket news", "mens"))
    assert [a.category for a in news.articles_from_feed(news_feed, settings)] == [
        "Mens",
        "Ticket News",
    ]


@pytest.mark.parametrize("bad", [None, [], {"data": "nope"}, {"meta": {}}])
def test_unexpected_feed_is_an_error(bad):
    with pytest.raises(FetchError):
        news.articles_from_feed(bad, Settings())


def test_requests_newest_first(monkeypatch, news_feed):
    seen = []

    def fake_get_json(url, headers=None, timeout=20):
        seen.append(url)
        return news_feed

    monkeypatch.setattr(news, "get_json", fake_get_json)
    assert len(news.fetch_news(Settings(news_page_size=7))) == 3
    assert "page.size=7" in seen[0]
    assert "sort=publishedDateTime%3Adesc" in seen[0]
