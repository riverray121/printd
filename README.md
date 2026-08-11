<p align="center"><img src="assets/logo.svg" width="140" alt="printd"></p>

# printd

A self-hosted print daemon. Send it a model, it slices with your profiles, enforces your rules, shows you a preview, prints on your go, and watches the print with snapshot notifications. Drive it from any MCP client (Claude, agents, your own tools) or the bundled CLI.

## Why

Printing through a chat agent usually means a long chain of manual steps executed differently every time. printd makes the pipeline deterministic: the agent makes decisions, the daemon does the work, and a print is three calls: `submit`, `slice`, `start`.

## How it works

```
submit (file or model URL)
  -> slice (your slicer, your profiles)
  -> gates (your rules: no brim, placement, bounds, ...)
  -> preview image -> human approval (overridable)
  -> start (preheat, print)
  -> watcher (snapshots, milestones, stall detection, notifications)
```

## The engine ships empty

Everything opinionated is a swappable part configured in one YAML file:

| Seam | Ships with |
|---|---|
| Printer drivers | OctoPrint |
| Slicer adapters | OrcaSlicer CLI |
| Gates | brim/skirt policy, placement zone, bounds check, preview approval |
| G-code transforms | fresh-mesh probe preamble, Marlin start-gcode patches |
| Notifiers | Home Assistant |

If a behavior can't be expressed as config on one of these seams, it doesn't belong in core.

## Quickstart

```sh
pip install printd
printd-server --config config.yaml   # MCP server (HTTP) + watcher
printctl status                      # same operations from the shell
```

See `example-config.yaml` for a full config.

## License

MIT
