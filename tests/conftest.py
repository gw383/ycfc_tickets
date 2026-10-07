import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ticket_feed():
    return json.loads((FIXTURES / "ticket_feed.json").read_text(encoding="utf-8"))


@pytest.fixture
def news_feed():
    return json.loads((FIXTURES / "news_feed.json").read_text(encoding="utf-8"))
