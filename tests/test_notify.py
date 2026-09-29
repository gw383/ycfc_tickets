import pytest

from ycfc_tickets import notify
from ycfc_tickets.config import Settings
from ycfc_tickets.notify import Alert, NtfyNotifier, build_notifier, fixtures_alert


def test_no_notifier_without_topic():
    assert build_notifier(Settings()) is None


def test_notifier_from_settings():
    n = build_notifier(Settings(ntfy_topic="ycfc-secret", ntfy_server="https://ntfy.example"))
    assert (n.topic, n.server) == ("ycfc-secret", "https://ntfy.example")


def test_rejects_non_http_server():
    with pytest.raises(ValueError):
        NtfyNotifier("t", "file:///etc")


def test_alert_wording():
    assert fixtures_alert(["A"], "u").title == "YCFC: new fixture on sale"
    two = fixtures_alert(["A", "B"], "u")
    assert two.title == "YCFC: 2 new fixtures on sale"
    assert two.body == "- A\n- B"


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b""


def test_ntfy_request(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["req"] = req
        return _Resp()

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    NtfyNotifier("my-topic", "https://ntfy.sh/", token="tk").send(
        Alert("Title – x", "body", "https://t")
    )
    req = captured["req"]
    assert req.full_url == "https://ntfy.sh/my-topic"
    assert req.data == b"body"
    assert req.get_header("Click") == "https://t"
    assert req.get_header("Title") == "Title  x"
    assert req.get_header("Authorization") == "Bearer tk"


def test_send_returns_false_on_network_error(monkeypatch):
    def boom(req, timeout):
        raise OSError("no network")

    monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
    assert notify.send(NtfyNotifier("t"), Alert("t", "b", "u")) is False
