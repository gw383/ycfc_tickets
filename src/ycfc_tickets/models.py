"""The two things we watch for: fixtures going on sale, and news articles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Fixture:
    name: str  # "York City v Port Vale"
    date_text: str = ""  # "Saturday 24th October - Kick Off 3pm", as the club wrote it
    category: str = ""  # "League Fixture"
    image_url: str | None = None


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    url: str
    category: str = ""
    published: datetime | None = None
    image_url: str | None = None
