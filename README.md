<p align="center"><img src="assets/logo.svg" width="140" alt="printd"></p>

# printd

A self-hosted print daemon. Send it a model file or URL, and it slices with your profiles, enforces your rules, renders a preview for approval, starts the print, and watches it, sending phone notifications with live camera photos at every stage. Drive it from any MCP client (Claude, other agents, your own tools) or the bundled CLI.

## How it works

```
submit (file or model URL)
  -> slice (your slicer, your profiles)
  -> checks (brim policy, bed placement, motion bounds)
  -> preview image -> approval (overridable per job)
  -> start (preheat, then print)
  -> watch (camera-photo notifications: first layer, milestones, stalls, done/failed)
```

The watcher never acts on its own: it photographs the print bed with your printer's camera and notifies you; pausing or cancelling stays a human decision.

## Suggested hardware setup

| Piece | Example | Role |
|---|---|---|
| Printer | Any Marlin printer with OctoPrint support (tested: Creality Ender-3 V3 SE) | Prints |
| Print server | Raspberry Pi 3B+/Zero 2 running OctoPrint, USB to the printer, camera attached | Feeds G-code to the printer, serves camera snapshots |
| printd host | Raspberry Pi 5 (2 GB+ RAM for slicing) or any Linux box | Runs printd: slicing, checks, previews, watcher, MCP server |

A single machine can play both server roles if it has the RAM to slice. Keeping them separate means nothing you add to the printd host can disturb a running print.

## Quickstart

```sh
pip install printd
printd-server --config config.yaml   # MCP server (HTTP)
printd-watch --config config.yaml    # watcher daemon
printctl status                      # same operations from the shell
```

Copy `example-config.yaml` and fill in your printer. printd authenticates to OctoPrint with an API key because OctoPrint requires one for all REST calls; copy it from OctoPrint under Settings → API.

Previews render as a single composite PNG: six shaded 3D views (extrusion tubes, per-feature colors), six transparent line projections, and a bed placement map. This needs Node plus a headless Chromium (`cd render3d && npm install && npm run build`, then `npx playwright install chromium` or point `PRINTD_CHROMIUM` at any Chromium binary). Without Node, printd falls back to a five-view SVG line render that only needs Chromium; the pipeline works either way.

## Swappable parts

Everything opinionated is configured, not hardcoded, in one YAML file:

| Seam | Ships with |
|---|---|
| Printer drivers | OctoPrint |
| Slicer adapters | OrcaSlicer CLI |
| Checks | brim/skirt policy, bed placement zone, motion bounds, preview approval |
| G-code transforms | fresh-bed-probe preamble, Marlin start-gcode patches |
| Notifiers | Home Assistant companion app |
| Power control | Home Assistant switch (on before start, off after finish + cooldown) |

## License

MIT
