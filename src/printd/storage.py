"""Filesystem layout and the job outcome log."""

import hashlib
import json
import time
from pathlib import Path


class Storage:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.inbox = self.root / "inbox"
        self.gcode = self.root / "gcode"
        self.previews = self.root / "previews"
        for d in (self.inbox, self.gcode, self.previews):
            d.mkdir(parents=True, exist_ok=True)
        self.jobs_log = self.root / "jobs.log"

    @staticmethod
    def file_hash(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    def log_job(self, **fields) -> None:
        fields.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        with open(self.jobs_log, "a") as f:
            f.write(json.dumps(fields) + "\n")
