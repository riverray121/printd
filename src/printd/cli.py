"""printctl: the same pipeline from a shell."""

import argparse
import json
import os
import sys
from pathlib import Path

from .config import Config
from .pipeline import Pipeline


def main():
    ap = argparse.ArgumentParser(prog="printctl", description="printd CLI")
    ap.add_argument("--config", default=os.environ.get("PRINTD_CONFIG"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("submit", help="bring a model file or URL into the inbox")
    s.add_argument("source")

    s = sub.add_parser("slice", help="slice a submitted model")
    s.add_argument("model")
    s.add_argument("--process", default="plain")
    s.add_argument("--filament", default="default")
    s.add_argument("--no-fresh-mesh", action="store_true")

    s = sub.add_parser("start", help="start a print")
    s.add_argument("gcode")
    s.add_argument("--token", default="")
    s.add_argument("--skip-approval", action="store_true")

    for name in ("status", "pause", "resume", "cancel"):
        sub.add_parser(name)

    s = sub.add_parser("snapshot", help="save a camera snapshot")
    s.add_argument("out", nargs="?", default="snapshot.jpg")

    s = sub.add_parser("light", help="printer work light")
    s.add_argument("state", choices=["on", "off", "status"])

    s = sub.add_parser("gcode", help="escape hatch: raw G-code")
    s.add_argument("commands", nargs="+")

    args = ap.parse_args()
    if not args.config:
        ap.error("--config or PRINTD_CONFIG required")
    p = Pipeline(Config.load(args.config))

    if args.cmd == "submit":
        print(p.submit(args.source))
    elif args.cmd == "slice":
        opts = {"fresh_mesh": False} if args.no_fresh_mesh else {}
        r = p.slice(args.model, args.process, args.filament, opts)
        print(json.dumps(r.__dict__, indent=2))
    elif args.cmd == "start":
        print(p.start(args.gcode, args.token or None, args.skip_approval))
    elif args.cmd == "status":
        print(json.dumps(p.status().as_dict(), indent=2))
    elif args.cmd == "pause":
        p.pause(); print("paused")
    elif args.cmd == "resume":
        p.resume(); print("resumed")
    elif args.cmd == "cancel":
        p.cancel(); print("cancelled")
    elif args.cmd == "snapshot":
        image = p.snapshot()
        if image is None:
            sys.exit("no camera available")
        Path(args.out).write_bytes(image)
        print(args.out)
    elif args.cmd == "light":
        if p.light is None:
            sys.exit("no light configured")
        if args.state == "on":
            p.light.on()
            print("on")
        elif args.state == "off":
            p.light.off()
            print("off")
        else:
            print(json.dumps({"on": p.light.is_on()}))
    elif args.cmd == "gcode":
        p.driver.gcode(args.commands)
        print("sent")


if __name__ == "__main__":
    main()
