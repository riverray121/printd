"""Bring a model into the inbox: local file path or URL.

Direct model-file URLs download as-is. Marketplace page URLs (Printables,
MakerWorld) are recognized and rejected with a clear message until their
download APIs are wired up.
"""

from pathlib import Path
from urllib.parse import urlparse

import requests

_MODEL_EXTS = (".stl", ".3mf")
_MARKETPLACES = ("printables.com", "makerworld.com")


def submit(source: str, inbox: Path) -> Path:
    if source.startswith(("http://", "https://")):
        return _from_url(source, inbox)
    src = Path(source).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"{source} not found")
    if src.suffix.lower() not in _MODEL_EXTS:
        raise ValueError(f"unsupported model type {src.suffix!r}; expected one of {_MODEL_EXTS}")
    dst = inbox / src.name
    dst.write_bytes(src.read_bytes())
    return dst


def _from_url(url: str, inbox: Path) -> Path:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name.lower().endswith(_MODEL_EXTS):
        host = parsed.netloc.lower()
        if any(m in host for m in _MARKETPLACES):
            raise ValueError(
                f"{host} page URLs are not supported yet; pass the model file's direct "
                "download URL (ends in .stl or .3mf)"
            )
        raise ValueError("URL must point at a model file (.stl or .3mf)")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    dst = inbox / name
    dst.write_bytes(r.content)
    return dst
