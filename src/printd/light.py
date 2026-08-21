"""Printer work light through an HTTP relay.

Configured via the ``light`` section; deployments without one simply have
no light. The ``http`` backend drives any relay that exposes plain on/off
endpoints (a GPIO proxy on the print server, a Tasmota plug, ...) and can
read state from a JSON status endpoint via ``status_url``/``status_key``.
"""

import requests


class HTTPLight:
    def __init__(self, cfg: dict):
        self.on_url = cfg["on_url"]
        self.off_url = cfg["off_url"]
        self.status_url = cfg.get("status_url")
        self.status_key = cfg.get("status_key", "on")
        self.method = cfg.get("method", "get").lower()
        self.timeout = int(cfg.get("http_timeout_s", 10))

    def _hit(self, url: str) -> None:
        requests.request(self.method, url, timeout=self.timeout).raise_for_status()

    def on(self) -> None:
        self._hit(self.on_url)

    def off(self) -> None:
        self._hit(self.off_url)

    def is_on(self) -> bool | None:
        """Current state, or None when the relay has no status endpoint."""
        if not self.status_url:
            return None
        r = requests.get(self.status_url, timeout=self.timeout)
        r.raise_for_status()
        return bool(r.json().get(self.status_key))


def make_light(cfg: dict) -> HTTPLight | None:
    if not cfg:
        return None
    backend = cfg.get("backend")
    if backend == "http":
        return HTTPLight(cfg)
    raise ValueError(f"unknown light backend {backend!r}")
