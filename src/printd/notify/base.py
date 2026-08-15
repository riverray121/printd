"""Notifier interface: an event, optionally with a snapshot image."""

from abc import ABC, abstractmethod


class Notifier(ABC):
    def __init__(self, cfg: dict):
        self.cfg = cfg

    @abstractmethod
    def send(self, title: str, message: str, image: bytes | None = None) -> None: ...

    def new_session(self) -> None:
        """A new print began; backends with per-print state reset it here."""
