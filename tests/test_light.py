import pytest

from printd import light as light_mod
from printd.light import HTTPLight, make_light


def test_no_section_means_no_light():
    assert make_light({}) is None


def test_unknown_backend_raises():
    with pytest.raises(ValueError):
        make_light({"backend": "zigbee"})


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_http_light_hits_urls_and_reads_status(monkeypatch):
    calls = []

    def fake_request(method, url, timeout):
        calls.append((method, url))
        return FakeResponse({})

    def fake_get(url, timeout):
        calls.append(("get", url))
        return FakeResponse({"manual_on": True})

    monkeypatch.setattr(light_mod.requests, "request", fake_request)
    monkeypatch.setattr(light_mod.requests, "get", fake_get)

    lt = HTTPLight({
        "on_url": "http://relay/on",
        "off_url": "http://relay/off",
        "status_url": "http://relay/status",
        "status_key": "manual_on",
    })
    lt.on()
    lt.off()
    assert lt.is_on() is True
    assert calls == [
        ("get", "http://relay/on"),
        ("get", "http://relay/off"),
        ("get", "http://relay/status"),
    ]


def test_http_light_without_status_url_reports_none():
    lt = HTTPLight({"on_url": "http://relay/on", "off_url": "http://relay/off"})
    assert lt.is_on() is None
