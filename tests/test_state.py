import json
from datetime import datetime, timedelta, timezone

from ycfc_tickets.state import FixtureState

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def test_missing_file_is_new(tmp_path):
    state = FixtureState.load(tmp_path / "state.json")
    assert state.is_new_file
    assert state.unseen(["A", "B"]) == ["A", "B"]


def test_round_trip(tmp_path):
    path = tmp_path / "nested" / "state.json"
    state = FixtureState.load(path)
    state.update(["York City v Barnet"], now=NOW)
    state.save(path)

    loaded = FixtureState.load(path)
    assert not loaded.is_new_file
    assert loaded.unseen(["York City v Barnet", "York City v Barrow"]) == ["York City v Barrow"]
    assert json.loads(path.read_text())["version"] == 1


def test_fixture_that_briefly_disappears_is_not_new_again(tmp_path):
    state = FixtureState()
    state.update(["A", "B"], now=NOW)
    state.update(["A"], now=NOW + timedelta(minutes=10))  # B missing on a flaky load
    assert state.unseen(["A", "B"]) == []


def test_first_seen_is_kept_and_last_seen_moves(tmp_path):
    state = FixtureState()
    state.update(["A"], now=NOW)
    state.update(["A"], now=NOW + timedelta(hours=1))
    entry = state.fixtures["A"]
    assert entry["first_seen"] == NOW.isoformat()
    assert entry["last_seen"] == (NOW + timedelta(hours=1)).isoformat()


def test_old_entries_are_forgotten():
    state = FixtureState()
    state.update(["Old"], now=NOW)
    state.update(["New"], now=NOW + timedelta(days=200))
    assert list(state.fixtures) == ["New"]
