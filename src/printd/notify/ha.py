"""Home Assistant companion-app notifier.

Snapshots are written into HA's ``www`` directory (shared volume or path) and
referenced as ``/local/...`` so the phone fetches them through HA itself.
"""

import time
from pathlib import Path

import requests

from .base import Notifier


class HomeAssistantNotifier(Notifier):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.url = cfg["ha_url"].rstrip("/")
        self.token = cfg["ha_token"]
        service = cfg.get("ha_notify_service", "notify.notify")
        self.service_path = service.replace(".", "/", 1)
        self.www_dir = Path(cfg.get("ha_www_dir", "/ha_www")) / "printd"
        self.click_url = cfg.get("octoprint_ui_url")

    def send(self, title: str, message: str, image: bytes | None = None) -> None:
        data: dict = {}
        if image is not None:
            try:
                self.www_dir.mkdir(parents=True, exist_ok=True)
                name = f"snap_{int(time.time())}.jpg"
                (self.www_dir / name).write_bytes(image)
                data["image"] = f"/local/printd/{name}"
            except OSError:
                pass  # HA www volume not mounted; send text-only
        if self.click_url:
            data["url"] = self.click_url
        payload = {"title": title, "message": message}
        if data:
            payload["data"] = data
        requests.post(
            f"{self.url}/api/services/{self.service_path}",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=15,
        ).raise_for_status()
