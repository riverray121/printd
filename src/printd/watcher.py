"""Print watcher: polls the printer, emits notifications, never acts alone.

Design rules learned the hard way:
- Heartbeat unconditionally on a fixed cadence. A monitor whose logging depends
  on conditions can silently fail while looking healthy.
- Always emit on every terminal state.
"""

import argparse
import sys
import time

from .config import Config
from .notify import make_notifier
from .pipeline import Pipeline

ACTIVE_STATES = ("Printing", "Paused", "Pausing", "Resuming")


class Watcher:
    def __init__(self, pipeline: Pipeline, notifier, cfg: dict):
        self.p = pipeline
        self.notifier = notifier
        self.poll_s = int(cfg.get("poll_seconds", 30))
        self.heartbeat_every = int(cfg.get("heartbeat_every_polls", 10))
        self.stall_polls = max(1, int(cfg.get("stall_minutes", 10)) * 60 // self.poll_s)
        self.first_layer_polls = max(1, int(cfg.get("first_layer_check_minutes", 10)) * 60 // self.poll_s)
        self.milestones = list(cfg.get("milestones", [25, 50, 75]))
        self._reset()

    def _reset(self):
        self.active_file = None
        self.polls_in_print = 0
        self.last_progress = -1.0
        self.stalled_for = 0
        self.sent_milestones = set()
        self.sent_first_layer = False
        self.stall_notified = False

    def _notify(self, title: str, message: str, with_snapshot: bool = True):
        image = self.p.snapshot() if with_snapshot else None
        try:
            self.notifier.send(title, message, image)
        except Exception as e:  # notification failure must never kill the watcher
            print(f"notify failed: {e}", file=sys.stderr, flush=True)

    def tick(self):
        try:
            st = self.p.status()
        except Exception as e:
            if self.active_file and not self.stall_notified:
                self._notify("Printer unreachable", f"status poll failed: {e}", with_snapshot=False)
                self.stall_notified = True
            return

        state = st.state
        if state in ACTIVE_STATES:
            if st.file != self.active_file:
                self._reset()
                self.active_file = st.file
                self._notify("Print started", f"{st.file}")
            self.polls_in_print += 1
            completion = st.completion or 0.0

            if self.polls_in_print % self.heartbeat_every == 0:
                left = f", ~{(st.time_left_s or 0) // 60} min left" if st.time_left_s else ""
                print(f"heartbeat: {st.file} {completion:.1f}%{left}", flush=True)

            if not self.sent_first_layer and self.polls_in_print >= self.first_layer_polls:
                self.sent_first_layer = True
                self._notify("First layer window over", f"{st.file} at {completion:.1f}%. Check the surface.")

            for m in self.milestones:
                if completion >= m and m not in self.sent_milestones:
                    self.sent_milestones.add(m)
                    left = f", ~{(st.time_left_s or 0) // 60} min left" if st.time_left_s else ""
                    self._notify(f"{m}% done", f"{st.file}{left}")

            if state == "Printing":
                if completion <= self.last_progress:
                    self.stalled_for += 1
                    if self.stalled_for >= self.stall_polls and not self.stall_notified:
                        self.stall_notified = True
                        self._notify("Possible stall", f"{st.file} stuck at {completion:.1f}%. Check the snapshot.")
                else:
                    self.stalled_for = 0
                    self.stall_notified = False
                self.last_progress = completion
        else:
            if self.active_file:
                finished = self.last_progress >= 99.0
                title = "Print finished" if finished else f"Print ended: {state}"
                self._notify(title, f"{self.active_file} ({self.last_progress:.1f}%)")
                self.p.storage.log_job(
                    event="finished" if finished else "ended",
                    file=self.active_file,
                    state=state,
                    completion=round(self.last_progress, 1),
                )
                self._reset()

    def run_forever(self):
        print(f"printd watcher up: polling every {self.poll_s}s", flush=True)
        while True:
            self.tick()
            time.sleep(self.poll_s)


def main():
    ap = argparse.ArgumentParser(description="printd watcher daemon")
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    config = Config.load(args.config)
    pipeline = Pipeline(config)
    notifier = make_notifier(config.section("notifier"))
    Watcher(pipeline, notifier, config.section("watcher")).run_forever()


if __name__ == "__main__":
    main()
