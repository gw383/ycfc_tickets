from dataclasses import dataclass, field

import pytest

from ycfc_tickets import cli
from ycfc_tickets.config import Settings
from ycfc_tickets.scraper import ScrapeError
from ycfc_tickets.state import FixtureState

PAGE_ONE = "York City v Northampton Town\nBUY TICKETS"
PAGE_TWO = "York City v Northampton Town\nYork City v Barnet\nYork City v Barnet: Parking"


@dataclass
class FakeNotifier:
    name: str = "fake"
    fail: bool = False
    sent: list = field(default_factory=list)

    def send(self, alert):
        if self.fail:
            raise RuntimeError("boom")
        self.sent.append(alert)


@pytest.fixture
def settings(tmp_path):
    return Settings(state_file=tmp_path / "state.json", log_file=None)


@pytest.fixture
def notifier(monkeypatch):
    fake = FakeNotifier()
    monkeypatch.setattr(cli, "build_notifier", lambda s: fake)
    return fake


def run(monkeypatch, settings, page_text, *argv):
    monkeypatch.setattr(cli, "fetch_page_text", lambda s, shot=None: page_text)
    return cli.run(settings, cli._parse_args(list(argv)))


def test_first_run_records_baseline_without_alert(monkeypatch, settings, notifier):
    assert run(monkeypatch, settings, PAGE_ONE) == cli.EXIT_OK
    assert notifier.sent == []
    assert list(FixtureState.load(settings.state_file).fixtures) == ["York City v Northampton Town"]


def test_alerts_only_for_new_fixture(monkeypatch, settings, notifier):
    run(monkeypatch, settings, PAGE_ONE)
    assert run(monkeypatch, settings, PAGE_TWO) == cli.EXIT_OK
    assert len(notifier.sent) == 1
    assert notifier.sent[0].body == "- York City v Barnet"

    run(monkeypatch, settings, PAGE_TWO)  # third run: nothing new
    assert len(notifier.sent) == 1


def test_failed_alert_is_retried_next_run(monkeypatch, settings, notifier):
    run(monkeypatch, settings, PAGE_ONE)
    notifier.fail = True
    assert run(monkeypatch, settings, PAGE_TWO) == cli.EXIT_ALERT_FAILED
    notifier.fail = False
    run(monkeypatch, settings, PAGE_TWO)
    assert [a.body for a in notifier.sent] == ["- York City v Barnet"]


def test_dry_run_sends_and_saves_nothing(monkeypatch, settings, notifier):
    run(monkeypatch, settings, PAGE_ONE)
    before = settings.state_file.read_text()
    run(monkeypatch, settings, PAGE_TWO, "--dry-run")
    assert notifier.sent == []
    assert settings.state_file.read_text() == before


def test_empty_page_leaves_state_alone(monkeypatch, settings, notifier):
    run(monkeypatch, settings, PAGE_ONE)
    before = settings.state_file.read_text()
    assert run(monkeypatch, settings, "Nothing on sale") == cli.EXIT_OK
    assert settings.state_file.read_text() == before


def test_scrape_failure_exit_code(monkeypatch, settings, notifier):
    def boom(s, shot=None):
        raise ScrapeError("down")

    monkeypatch.setattr(cli, "fetch_page_text", boom)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    assert cli.run(settings, cli._parse_args([])) == cli.EXIT_SCRAPE_FAILED


def test_missing_topic_keeps_fixture_unseen(monkeypatch, settings):
    monkeypatch.setattr(cli, "build_notifier", lambda s: None)
    run(monkeypatch, settings, PAGE_ONE)
    assert run(monkeypatch, settings, PAGE_TWO) == cli.EXIT_ALERT_FAILED
    assert "York City v Barnet" not in FixtureState.load(settings.state_file).fixtures


def test_test_alert(monkeypatch, settings, notifier):
    assert cli.run(settings, cli._parse_args(["--test-alert"])) == cli.EXIT_OK
    assert notifier.sent[0].title.endswith("test alert")
