"""MCP face: the same pipeline over streamable HTTP for agent clients."""

import argparse
import base64
import os
from pathlib import Path

from fastmcp import FastMCP

from .config import Config
from .pipeline import Pipeline

mcp = FastMCP("printd")
_pipeline: Pipeline | None = None


def pipeline() -> Pipeline:
    assert _pipeline is not None, "server not initialized"
    return _pipeline


@mcp.tool
def submit(source: str) -> str:
    """Bring a model into printd. Accepts a local path on the server or a
    direct URL to an .stl/.3mf file. Returns the inbox path to pass to slice."""
    return str(pipeline().submit(source))


@mcp.tool
def slice_model(model: str, process: str = "plain", filament: str = "default",
                fresh_mesh: bool | None = None) -> dict:
    """Slice a submitted model. process and filament name entries from the
    config's process_profiles / filament_profiles maps (e.g. plain, supports,
    strong; default, hotbond). Returns gcode path, preview image path, the
    approval token required by start, gate notes, and placement notes."""
    opts = {}
    if fresh_mesh is not None:
        opts["fresh_mesh"] = fresh_mesh
    result = pipeline().slice(model, process, filament, opts)
    return result.__dict__


@mcp.tool
def preview_image(gcode: str) -> dict:
    """Return the preview PNG for a sliced file, base64-encoded, so the client
    can show it to the human for approval."""
    p = pipeline()
    png = p.storage.previews / f"{Path(gcode).stem}.png"
    if not png.exists():
        raise FileNotFoundError("no preview rendered for that file; run slice first")
    return {"png_base64": base64.b64encode(png.read_bytes()).decode(), "path": str(png)}


@mcp.tool
def start(gcode: str, approval_token: str = "", skip_approval: bool = False) -> str:
    """Start a print. Requires the approval token from slice unless
    skip_approval is explicitly requested by the human."""
    return pipeline().start(gcode, approval_token or None, skip_approval)


@mcp.tool
def status() -> dict:
    """Printer and job state: temperatures, progress, time left."""
    return pipeline().status().as_dict()


@mcp.tool
def snapshot() -> dict:
    """Camera snapshot. Saves the JPEG to the returned path (for clients that
    attach files) and includes it base64-encoded (for clients that render
    inline)."""
    image = pipeline().snapshot()
    if image is None:
        return {"error": "no camera configured or camera unreachable"}
    path = Path("/tmp/printd_snapshot.jpg")
    path.write_bytes(image)
    return {"path": str(path), "jpeg_base64": base64.b64encode(image).decode()}


@mcp.tool
def pause() -> str:
    """Pause the running print."""
    pipeline().pause()
    return "paused"


@mcp.tool
def resume() -> str:
    """Resume a paused print."""
    pipeline().resume()
    return "resumed"


@mcp.tool
def cancel() -> str:
    """Cancel the print, shut heaters off, and park the head."""
    pipeline().cancel()
    return "cancelled (heaters off, head parked)"


@mcp.tool
def send_gcode(commands: list[str]) -> str:
    """Escape hatch: send raw G-code commands. Use only when the human has
    asked for something the other tools cannot do."""
    driver = pipeline().driver
    if not hasattr(driver, "gcode"):
        raise RuntimeError("driver does not support raw G-code")
    driver.gcode(commands)
    return f"sent {len(commands)} command(s)"


def main():
    global _pipeline
    ap = argparse.ArgumentParser(description="printd MCP server")
    ap.add_argument("--config", default=os.environ.get("PRINTD_CONFIG"), required=False)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8756)
    args = ap.parse_args()
    if not args.config:
        ap.error("--config or PRINTD_CONFIG required")
    _pipeline = Pipeline(Config.load(args.config))

    token = os.environ.get("PRINTD_BEARER_TOKEN")
    if token:
        try:
            from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

            mcp.auth = StaticTokenVerifier(tokens={token: {"client_id": "printd"}})
        except ImportError as e:
            # A token was configured, so serving without the check would
            # expose start/cancel/send_gcode to the whole network. Refuse
            # to start instead.
            raise SystemExit(
                f"PRINTD_BEARER_TOKEN is set but the fastmcp auth provider "
                f"failed to load ({e}); refusing to serve unauthenticated"
            )
    mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
