"""Latest articles from the club website's news feed (the one its News page uses)."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

from ycfc_tickets.config import Settings
from ycfc_tickets.http import FetchError, browser_headers, get_json
from ycfc_tickets.models import Article

IMAGE_HOST = "https://images.gc.yorkcityfcservices.co.uk/"


def _parse_time(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def articles_from_feed(data: object, settings: Settings) -> list[Article]:
    """Turn the news feed into articles (newest first), keeping only wanted categories."""
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise FetchError("News feed wasn't in the expected format")

    wanted = {c.lower() for c in settings.news_categories}
    articles: list[Article] = []
    for item in data["data"]:
        attrs = item.get("attributes") if isinstance(item, dict) else None
        if not isinstance(attrs, dict):
            continue
        post_id = str(attrs.get("postID") or item.get("id") or "")
        title = " ".join(str(attrs.get("postTitle") or "").split())
        slug = str(attrs.get("postSlug") or "")
        if not (post_id and title and slug):
            continue
        if str(attrs.get("postStatus") or "Published") != "Published":
            continue
        category = str(attrs.get("postCategoryName") or "")
        if wanted and category.lower() not in wanted:
            continue
        image_id = attrs.get("mediaLibraryID")
        articles.append(
            Article(
                id=post_id,
                title=title,
                url=settings.site_url.rstrip("/") + "/" + slug.lstrip("/"),
                category=category,
                published=_parse_time(attrs.get("publishedDateTime")),
                # The image service resizes on request; .webp keeps it small for phones.
                image_url=f"{IMAGE_HOST}fit-in/1200x675/{image_id}.webp" if image_id else None,
            )
        )
    return articles


def fetch_news(settings: Settings) -> list[Article]:
    """The most recent articles, newest first. Raises FetchError if they can't be read."""
    query = urlencode(
        {"page.size": settings.news_page_size, "page.number": 1, "sort": "publishedDateTime:desc"}
    )
    data = get_json(f"{settings.news_api_url}?{query}", browser_headers(settings.site_url))
    return articles_from_feed(data, settings)
