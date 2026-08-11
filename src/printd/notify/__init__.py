from .base import Notifier
from .ha import HomeAssistantNotifier
from .log import LogNotifier

_NOTIFIERS = {"ha": HomeAssistantNotifier, "log": LogNotifier}


def make_notifier(cfg: dict) -> Notifier:
    name = cfg.get("backend", "log")
    try:
        return _NOTIFIERS[name](cfg)
    except KeyError:
        raise ValueError(f"unknown notifier backend {name!r}") from None
