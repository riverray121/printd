"""Home Assistant companion-app notifier.

Snapshots are written into HA's ``www`` directory (shared volume or path) and
referenced as ``/local/...`` so the phone fetches them through HA itself.

Each print gets a session gallery: every snapshot sent during the print is
kept under ``www/printd/session/`` next to a generated ``gallery.html``
(newest first, with the notification captions). ``new_session()`` wipes the
folder, so the gallery always shows the current print — or the last one,
until the next print starts. Notification taps open the gallery when
``gallery_url`` is configured.
"""

import html
import json
import time
from pathlib import Path

import requests

from .base import Notifier

_GALLERY_STYLE = """
body { font-family: sans-serif; background: #111; color: #ddd; margin: 0 auto;
       padding: 12px; max-width: 680px; }
h1 { font-size: 16px; font-weight: 600; }
figure { margin: 0 0 18px 0; }
img { width: 100%; border-radius: 6px; display: block; }
figcaption { font-size: 13px; color: #aaa; padding: 4px 2px; }
p { font-size: 14px; }
"""


class HomeAssistantNotifier(Notifier):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.url = cfg["ha_url"].rstrip("/")
        self.token = cfg["ha_token"]
        service = cfg.get("ha_notify_service", "notify.notify")
        self.service_path = service.replace(".", "/", 1)
        self.www_dir = Path(cfg.get("ha_www_dir", "/ha_www")) / "printd"
        self.session_dir = self.www_dir / "session"
        self.click_url = cfg.get("octoprint_ui_url")
        self.gallery_url = cfg.get("gallery_url")

    # -- session gallery ---------------------------------------------------

    def new_session(self) -> None:
        """Start a fresh snapshot gallery; called when a new print begins."""
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            for f in self.session_dir.iterdir():
                f.unlink()
            self._write_gallery([])
        except OSError:
            pass  # HA www volume not mounted; galleries just stay disabled

    def _manifest(self) -> list[dict]:
        p = self.session_dir / "manifest.json"
        try:
            return json.loads(p.read_text())
        except (OSError, ValueError):
            return []

    def _record_snapshot(self, name: str, title: str, message: str) -> None:
        entries = self._manifest()
        entries.append({"file": name, "title": title, "message": message, "ts": time.time()})
        (self.session_dir / "manifest.json").write_text(json.dumps(entries))
        self._write_gallery(entries)

    def _write_gallery(self, entries: list[dict]) -> None:
        figures = []
        for e in reversed(entries):
            stamp = time.strftime("%H:%M", time.localtime(e["ts"]))
            caption = f"{stamp} — {e['title']}: {e['message']}"
            figures.append(
                f'<figure><img src="{e["file"]}" loading="lazy">'
                f"<figcaption>{html.escape(caption)}</figcaption></figure>"
            )
        body = "\n".join(figures) if figures else "<p>No snapshots yet this print.</p>"
        page = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<meta http-equiv='refresh' content='60'>"
            f"<title>printd snapshots</title><style>{_GALLERY_STYLE}</style></head>"
            f"<body><h1>printd snapshots</h1>\n{body}\n</body></html>"
        )
        (self.session_dir / "gallery.html").write_text(page)

    # -- sending -----------------------------------------------------------

    def send(self, title: str, message: str, image: bytes | None = None) -> None:
        data: dict = {}
        if image is not None:
            try:
                self.session_dir.mkdir(parents=True, exist_ok=True)
                name = f"snap_{int(time.time())}.jpg"
                (self.session_dir / name).write_bytes(image)
                self._record_snapshot(name, title, message)
                data["image"] = f"/local/printd/session/{name}"
                # Tap opens this print's snapshot gallery (or the image when
                # no gallery view is configured); the printer UI stays one
                # press away as an action in the expanded notification.
                data["url"] = self.gallery_url or data["image"]
                if self.click_url:
                    data["actions"] = [
                        {"action": "URI", "title": "Open printer hub", "uri": self.click_url}
                    ]
            except OSError:
                pass  # HA www volume not mounted; send text-only
        if "url" not in data and self.click_url:
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
