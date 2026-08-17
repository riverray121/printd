"""Printer power control through a Home Assistant switch.

Configured via the ``power`` section. With ``on_before_start`` the pipeline
switches the printer on before connecting; with ``off_after_finish`` the
watcher switches it off after a print completes and the nozzle has cooled
below ``cooldown_nozzle_c`` (cutting power hot stops the hotend fan while
heat is still draining out of the hotend).
"""

import requests


class HAPower:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.url = cfg["ha_url"].rstrip("/")
        self.token = cfg["ha_token"]
        self.entity = cfg["entity"]

    def _call(self, service: str) -> None:
        requests.post(
            f"{self.url}/api/services/switch/{service}",
            json={"entity_id": self.entity},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=15,
        ).raise_for_status()

    def on(self) -> None:
        self._call("turn_on")

    def off(self) -> None:
        self._call("turn_off")

    @property
    def on_before_start(self) -> bool:
        return bool(self.cfg.get("on_before_start", True))

    @property
    def off_after_finish(self) -> bool:
        return bool(self.cfg.get("off_after_finish", True))

    @property
    def cooldown_nozzle_c(self) -> float:
        return float(self.cfg.get("cooldown_nozzle_c", 50))


def make_power(cfg: dict) -> HAPower | None:
    if not cfg:
        return None
    backend = cfg.get("backend")
    if backend == "ha":
        return HAPower(cfg)
    raise ValueError(f"unknown power backend {backend!r}")
