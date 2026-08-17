"""Printer power control through a Home Assistant switch.

Configured via the ``power`` section. With ``on_before_start`` the pipeline
switches the printer on before connecting; with ``off_after_finish`` the
watcher switches it off after a print completes and the nozzle has cooled
below ``cooldown_nozzle_c`` (cutting power hot stops the hotend fan while
heat is still draining out of the hotend).
"""

import time

import requests


class HAPower:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.url = cfg["ha_url"].rstrip("/")
        self.token = cfg["ha_token"]
        self.entity = cfg["entity"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def _state(self) -> str:
        r = requests.get(
            f"{self.url}/api/states/{self.entity}", headers=self._headers(), timeout=15,
        )
        r.raise_for_status()
        return r.json()["state"]

    def _switch(self, service: str, want: str) -> None:
        """Command the switch and verify it actually changed.

        HA reports success even when the Matter command to the device times
        out, so the only trustworthy signal is the entity's state. Matter
        plugs drop occasional commands; retrying until the state matches
        makes the operation reliable.
        """
        for _ in range(6):
            requests.post(
                f"{self.url}/api/services/switch/{service}",
                json={"entity_id": self.entity},
                headers=self._headers(),
                timeout=15,
            ).raise_for_status()
            time.sleep(5)
            if self._state() == want:
                return
        raise TimeoutError(f"{self.entity} did not reach state {want!r} after retries")

    def on(self) -> None:
        self._switch("turn_on", "on")

    def off(self) -> None:
        self._switch("turn_off", "off")

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
