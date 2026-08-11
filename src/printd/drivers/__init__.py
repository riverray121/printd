from .base import Driver
from .octoprint import OctoPrintDriver

_DRIVERS = {"octoprint": OctoPrintDriver}


def make_driver(cfg: dict) -> Driver:
    name = cfg.get("driver", "octoprint")
    try:
        return _DRIVERS[name](cfg)
    except KeyError:
        raise ValueError(f"unknown printer driver {name!r}") from None
