from ycfc_tickets.config import DEFAULT_EXCLUDE
from ycfc_tickets.parser import parse_fixtures

# Text as rendered by the Future Ticketing widget (see tests/fixtures/tickets_page.html)
PAGE_TEXT = """
0 Item(s) Added
York City v Northampton Town
BUY TICKETS
York City v Accrington Stanley
BUY TICKETS
York City v Accrington Stanley: Parking
BUY TICKETS
Tickets supplied by Future Ticketing
"""


def test_extracts_fixtures_in_page_order():
    assert parse_fixtures(PAGE_TEXT, exclude_keywords=DEFAULT_EXCLUDE) == [
        "York City v Northampton Town",
        "York City v Accrington Stanley",
    ]


def test_skips_add_on_products():
    text = "York City v Barnet: Parking\nYork City v Barnet - Hospitality\nYork City v Barnet"
    assert parse_fixtures(text, exclude_keywords=DEFAULT_EXCLUDE) == ["York City v Barnet"]


def test_handles_vs_variants_and_whitespace():
    text = "  York City   vs.  Oldham Athletic \nYORK CITY V Barrow\nYork City v Crewe Alexandra"
    assert parse_fixtures(text) == [
        "York City v Oldham Athletic",
        "York City v Barrow",
        "York City v Crewe Alexandra",
    ]


def test_new_opponents_need_no_config():
    # Cup draws against unexpected teams are picked up without editing a team list.
    assert parse_fixtures("York City v Manchester United") == ["York City v Manchester United"]


def test_ignores_away_games_and_other_text():
    text = "Rochdale v York City\nYork City Ladies news\nBuy York City v shirts"
    assert parse_fixtures(text) == []


def test_deduplicates():
    assert parse_fixtures("York City v Barnet\nYork City v Barnet") == ["York City v Barnet"]


def test_configurable_home_team():
    assert parse_fixtures("Hull City v Leeds United", home_team="Hull City") == [
        "Hull City v Leeds United"
    ]
