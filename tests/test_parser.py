from ycfc_tickets.config import DEFAULT_EXCLUDE
from ycfc_tickets.models import Fixture
from ycfc_tickets.parser import fixture_name, parse_fixtures

# Text as rendered by the Future Ticketing widget (see tests/fixtures/tickets_page.html)
PAGE_TEXT = """
0 Item(s) Added
York City v Port Vale: Parking
Saturday 24th October - Kick Off 3PM
BUY TICKETS
York City v Northampton Town
Saturday 10th October - Kick Off 3pm
BUY TICKETS
York City v Accrington Stanley
BUY TICKETS
Tickets supplied by Future Ticketing
"""


def test_extracts_fixtures_in_page_order_with_dates():
    assert parse_fixtures(PAGE_TEXT, exclude_keywords=DEFAULT_EXCLUDE) == [
        Fixture("York City v Northampton Town", "Saturday 10th October - Kick Off 3pm"),
        Fixture("York City v Accrington Stanley", ""),  # next line isn't a date
    ]


def test_skips_add_on_products():
    assert fixture_name("York City v Barnet: Parking") is None
    assert (
        fixture_name("York City v Barnet - Hospitality", exclude_keywords=DEFAULT_EXCLUDE) is None
    )
    assert (
        fixture_name("York City v Barnet", exclude_keywords=DEFAULT_EXCLUDE) == "York City v Barnet"
    )


def test_category_can_rule_a_listing_out():
    assert (
        fixture_name("York City v Barnet", exclude_keywords=("parking",), category="Car Parking")
        is None
    )


def test_handles_vs_variants_and_whitespace():
    assert fixture_name("  York City   vs.  Oldham Athletic ") == "York City v Oldham Athletic"
    assert fixture_name("YORK CITY V Barrow") == "York City v Barrow"
    assert fixture_name("York City v Crewe Alexandra") == "York City v Crewe Alexandra"


def test_new_opponents_need_no_config():
    # Cup draws against unexpected teams are picked up without editing a team list.
    assert fixture_name("York City v Manchester United") == "York City v Manchester United"


def test_ignores_away_games_and_other_text():
    for line in ("Rochdale v York City", "York City Ladies news", "Buy York City v shirts"):
        assert fixture_name(line) is None


def test_deduplicates():
    assert len(parse_fixtures("York City v Barnet\nYork City v Barnet")) == 1


def test_configurable_home_team():
    assert (
        fixture_name("Hull City v Leeds United", home_team="Hull City")
        == "Hull City v Leeds United"
    )
