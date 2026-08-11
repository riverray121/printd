"""Stdout notifier for development and tests."""

import sys
import time

from .base import Notifier


class LogNotifier(Notifier):
    def send(self, title: str, message: str, image: bytes | None = None) -> None:
        stamp = time.strftime("%H:%M:%S")
        img = f" [snapshot {len(image)}B]" if image else ""
        print(f"[{stamp}] NOTIFY {title}: {message}{img}", file=sys.stderr, flush=True)
