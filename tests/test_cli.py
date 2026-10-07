from dataclasses import dataclass, field

import pytest

from ycfc_tickets import cli
from ycfc_tickets.config import Settings
from ycfc_tickets.http import FetchError
from ycfc_tickets.models import Article, Fixture
from ycfc_tickets.state import State

NORTHAMPTON = Fixture("York City v Northampton Town", "Saturday 10th October - Kick Off 3pm")
BARNET = Fixture("York City v Barnet", "Saturday 31st October - Kick Off 3pm")


def article(n: int) -> Article:
    return Article(id=f"id-{n}", title=f"Story {n}", url=f"https://club.example/news/{n}/")


@dataclass
class FakeNotifier:
    fail_titles: set = field(default_factory=set)
    sent: list = field(default_factory=list)

    def send(self, alert):
        if alert.title in self.fail_titles or "*" in self.fail_titles:
            raise RuntimeError("boom")
        self.sent.append(alert)

    @property
    def titles(self):
        return [a.title for a in self.sent]


@pytest.fixture
def settings(tmp_path):
    return Settings(state_file=tmp_path / "state.json", log_file=None)


@pytest.fixture
def notifier(monkeypatch):
    fake = FakeNotifier()
    monkeypatch.setattr(cli, "build_notifier", lambda s: fake)
    return fake


def run(monkeypatch, settings, fixtures, articles, *argv):
    """One check with the site returning these fixtures and articles (newest article first)."""

    def fetch(value):
        def _fetch(s):
            if isinstance(value, Exception):
                raise value
            return list(value)

        return _fetch

    monkeypatch.setattr(cli, "fetch_fixtures", fetch(fixtures))
    monkeypatch.setattr(cli, "fetch_news", fetch(articles))
    return cli.run(settings, cli._parse_args(list(argv)))


def test_first_run_records_baseline_without_alert(monkeypatch, settings, notifier):
    assert run(monkeypatch, settings, [NORTHAMPTON], [article(1)]) == cli.EXIT_OK
    assert notifier.sent == []
    state = State.load(settings.state_file)
    assert list(state.sections["fixtures"]) == ["York City v Northampton Town"]
    assert list(state.sections["news"]) == ["id-1"]


def test_alerts_only_for_new_fixture_and_article(monkeypatch, settings, notifier):
    run(monkeypatch, settings, [NORTHAMPTON], [article(1)])
    assert (
        run(monkeypatch, settings, [NORTHAMPTON, BARNET], [article(2), article(1)]) == cli.EXIT_OK
    )
    assert notifier.titles == ["Tickets on sale: York City v Barnet", "Story 2"]

    run(monkeypatch, settings, [NORTHAMPTON, BARNET], [article(2), article(1)])  # nothing new
    assert len(notifier.sent) == 2


def test_news_is_sent_oldest_first(monkeypatch, settings, notifier):
    run(monkeypatch, settings, [], [article(1)])
    run(monkeypatch, settings, [], [article(3), article(2), article(1)])
    assert notifier.titles == ["Story 2", "Story 3"]


def test_news_flood_is_capped(monkeypatch, settings, notifier):
    settings = Settings(state_file=settings.state_file, log_file=None, news_max_alerts=2)
    run(monkeypatch, settings, [], [article(1)])
    run(monkeypatch, settings, [], [article(n) for n in (6, 5, 4, 3, 2, 1)])
    assert notifier.titles == ["Story 5", "Story 6"]
    run(monkeypatch, settings, [], [article(n) for n in (6, 5, 4, 3, 2, 1)])
    assert len(notifier.sent) == 2  # the skipped ones aren't sent later either


def test_adding_news_to_an_existing_setup_does_not_spam(monkeypatch, settings, notifier):
    settings = Settings(state_file=settings.state_file, log_file=None, news_enabled=False)
    run(monkeypatch, settings, [NORTHAMPTON], [])
    with_news = Settings(state_file=settings.state_file, log_file=None)
    run(monkeypatch, with_news, [NORTHAMPTON], [article(2), article(1)])
    assert notifier.sent == []


def test_failed_alert_is_retried_next_run(monkeypatch, settings, notifier):
    run(monkeypatch, settings, [NORTHAMPTON], [article(1)])
    notifier.fail_titles = {"Story 2"}
    result = run(monkeypatch, settings, [NORTHAMPTON, BARNET], [article(2), article(1)])
    assert result == cli.EXIT_ALERT_FAILED
    assert notifier.titles == ["Tickets on sale: York City v Barnet"]

    notifier.fail_titles = set()
    assert (
        run(monkeypatch, settings, [NORTHAMPTON, BARNET], [article(2), article(1)]) == cli.EXIT_OK
    )
    assert notifier.titles == ["Tickets on sale: York City v Barnet", "Story 2"]


def test_dry_run_sends_and_saves_nothing(monkeypatch, settings, notifier):
    run(monkeypatch, settings, [NORTHAMPTON], [article(1)])
    before = settings.state_file.read_text()
    run(monkeypatch, settings, [NORTHAMPTON, BARNET], [article(2), article(1)], "--dry-run")
    assert notifier.sent == []
    assert settings.state_file.read_text() == before


def test_nothing_on_sale_is_fine(monkeypatch, settings, notifier):
    assert run(monkeypatch, settings, [], [article(1)]) == cli.EXIT_OK
    assert run(monkeypatch, settings, [BARNET], [article(1)]) == cli.EXIT_OK
    assert notifier.titles == ["Tickets on sale: York City v Barnet"]


def test_one_feed_failing_does_not_stop_the_other(monkeypatch, settings, notifier):
    run(monkeypatch, settings, [NORTHAMPTON], [article(1)])
    result = run(monkeypatch, settings, FetchError("down"), [article(2), article(1)])
    assert result == cli.EXIT_FETCH_FAILED
    assert notifier.titles == ["Story 2"]
    # ...and the fixtures we already knew about are still remembered
    assert "York City v Northampton Town" in State.load(settings.state_file).sections["fixtures"]


def test_missing_topic_keeps_items_unseen(monkeypatch, settings):
    monkeypatch.setattr(cli, "build_notifier", lambda s: None)
    run(monkeypatch, settings, [NORTHAMPTON], [article(1)])
    assert run(monkeypatch, settings, [NORTHAMPTON, BARNET], [article(1)]) == cli.EXIT_ALERT_FAILED
    assert "York City v Barnet" not in State.load(settings.state_file).sections["fixtures"]


def test_switches_turn_each_half_off(monkeypatch, settings, notifier):
    settings = Settings(state_file=settings.state_file, log_file=None, tickets_enabled=False)
    run(monkeypatch, settings, FetchError("should not be called"), [article(1)])
    assert "fixtures" not in State.load(settings.state_file).sections


def test_test_alert_uses_latest_real_items(monkeypatch, settings, notifier):
    assert run(monkeypatch, settings, [BARNET], [article(9)], "--test-alert") == cli.EXIT_OK
    assert notifier.titles == ["Tickets on sale: York City v Barnet", "Story 9"]
    assert not settings.state_file.exists()  # a test never touches saved state


def test_test_alert_falls_back_to_samples(monkeypatch, settings, notifier):
    assert run(monkeypatch, settings, FetchError("down"), [], "--test-alert") == cli.EXIT_OK
    assert len(notifier.sent) == 2


def test_repeated_failures_are_reported_once_then_recovery(monkeypatch, settings, notifier):
    run(monkeypatch, settings, [NORTHAMPTON], [article(1)])
    down = FetchError("blocked")

    for _ in range(cli.FAILURES_BEFORE_WARNING - 1):
        assert run(monkeypatch, settings, down, [article(1)]) == cli.EXIT_FETCH_FAILED
    assert notifier.sent == []  # a blip or two isn't worth a notification

    run(monkeypatch, settings, down, [article(1)])
    assert notifier.titles == ["YCFC checker needs a look"]
    assert "ticket list" in notifier.sent[0].body

    saved = settings.state_file.read_text()
    run(monkeypatch, settings, down, [article(1)])
    assert len(notifier.sent) == 1  # not nagged again
    assert settings.state_file.read_text() == saved  # and no pointless state updates

    assert run(monkeypatch, settings, [NORTHAMPTON], [article(1)]) == cli.EXIT_OK
    assert notifier.titles[-1] == "YCFC checker is working again"
    assert "problems" not in State.load(settings.state_file).sections


def test_single_blip_recovers_silently(monkeypatch, settings, notifier):
    run(monkeypatch, settings, [NORTHAMPTON], [article(1)])
    run(monkeypatch, settings, [NORTHAMPTON], FetchError("timeout"))
    run(monkeypatch, settings, [NORTHAMPTON], [article(1)])
    assert notifier.sent == []


def test_problem_alert_links_to_the_github_run(monkeypatch, settings):
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "gw383/ycfc_tickets")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    assert cli._run_url(settings) == "https://github.com/gw383/ycfc_tickets/actions/runs/42"
