import json

from ycfc_tickets.state import MAX_PER_SECTION, State


def test_missing_file_means_first_run(tmp_path):
    state = State.load(tmp_path / "state.json")
    assert state.is_first_run("fixtures")
    assert state.unseen("fixtures", ["A", "B"]) == ["A", "B"]


def test_round_trip(tmp_path):
    path = tmp_path / "nested" / "state.json"
    state = State.load(path)
    state.mark_seen("fixtures", {"York City v Barnet": "York City v Barnet"})
    assert state.save(path) is True

    loaded = State.load(path)
    assert not loaded.is_first_run("fixtures")
    assert loaded.is_first_run("news")  # never recorded, so news would baseline
    assert loaded.unseen("fixtures", ["York City v Barnet", "York City v Barrow"]) == [
        "York City v Barrow"
    ]
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2


def test_file_is_only_rewritten_when_something_new_is_seen(tmp_path):
    path = tmp_path / "state.json"
    state = State.load(path)
    state.mark_seen("news", {"1": "First"})
    state.save(path)

    again = State.load(path)
    again.mark_seen("news", {"1": "First"})
    assert again.save(path) is False
    again.mark_seen("news", {"2": "Second"})
    assert again.save(path) is True


def test_item_that_briefly_disappears_is_not_new_again():
    state = State()
    state.mark_seen("fixtures", {"A": "A", "B": "B"})
    state.mark_seen("fixtures", {"A": "A"})  # B missing on a flaky load
    assert state.unseen("fixtures", ["A", "B"]) == []


def test_empty_first_run_still_counts_as_recorded():
    state = State()
    state.mark_seen("fixtures", {})
    assert not state.is_first_run("fixtures")


def test_reads_the_older_file_format(tmp_path):
    path = tmp_path / "seen_fixtures.json"
    old = {"version": 1, "fixtures": {"York City v Barnet": {"first_seen": "x", "last_seen": "y"}}}
    path.write_text(json.dumps(old), encoding="utf-8")
    state = State.load(path)
    assert state.unseen("fixtures", ["York City v Barnet"]) == []
    assert state.is_first_run("news")


def test_old_entries_are_forgotten():
    state = State()
    for i in range(MAX_PER_SECTION + 25):
        state.sections.setdefault("news", {})[str(i)] = {"first_seen": f"{i:06d}", "label": ""}
    state.mark_seen("news", {"newest": "x"})
    assert len(state.sections["news"]) == MAX_PER_SECTION
    assert "0" not in state.sections["news"]
    assert "newest" in state.sections["news"]
