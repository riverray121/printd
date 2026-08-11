"""Config loading with ${ENV_VAR} interpolation."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _interpolate(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


@dataclass
class Config:
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(raw=_interpolate(data))

    def section(self, name: str) -> dict:
        value = self.raw.get(name) or {}
        if not isinstance(value, dict):
            raise ValueError(f"config section {name!r} must be a mapping")
        return value

    @property
    def storage_root(self) -> Path:
        return Path(self.section("storage").get("root", "~/print")).expanduser()
