"""Run the local Blender MCP server or its browser demonstration."""

import argparse
import json
import logging
import struct
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from mcp import Client
from mcp.server import MCPServer
from pydantic import JsonValue
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "artifacts/blender-mcp-demo"
MCP_PORT = 19840
WEB_PORT = 19841
MCP_URL = f"http://127.0.0.1:{MCP_PORT}/mcp"
TOOL = "build_key_door_scene"
ASSETS = ("key-door.blend", "key-door.glb", "preview.png")
IUNO_ASSETS = ("iuno-chibi.blend", "iuno-chibi.glb", "preview.png", "grid-preview.png")
logger = logging.getLogger(__name__)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


def validate_assets(folder: Path, names: tuple[str, ...] = ASSETS) -> dict[str, int]:
    blend_name, glb_name, *previews = names
    sizes = {name: (folder / name).stat().st_size for name in names}
    with (folder / glb_name).open("rb") as glb:
        header = glb.read(12)
    if (
        header != struct.pack("<4sII", b"glTF", 2, sizes[glb_name])
        or sizes[glb_name] <= 12
        or sizes[blend_name] == 0
    ):
        raise ValueError("Invalid Blender export")
    for name in previews:
        with (folder / name).open("rb") as png:
            if png.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Invalid Blender preview")
    return sizes


def serve_mcp(blender: Path) -> None:
    server = MCPServer("AgentLabyrinth GridWorld Blender Assets")

    def build_assets(scene: str, script: str, names: tuple[str, ...]) -> dict[str, JsonValue]:
        run_id = str(uuid4())
        folder = DEMO / "runs" / run_id
        folder.mkdir(parents=True)
        try:
            with (folder / "blender.log").open("wb") as log:
                subprocess.run(
                    [
                        str(blender),
                        "--background",
                        "--factory-startup",
                        "--python-exit-code",
                        "1",
                        "--threads",
                        "4",
                        "--python",
                        str(ROOT / "scripts" / script),
                        "--",
                        str(folder),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=True,
                    timeout=120,
                )
            sizes = validate_assets(folder, names)
        except (OSError, ValueError, subprocess.SubprocessError):
            logger.exception("Blender failed in run %s", run_id)
            raise RuntimeError(f"Blender 执行失败。诊断编号 {run_id}") from None
        (folder / "ready").touch()
        return {"scene": scene, "run_id": run_id, "bytes": dict(sizes)}

    @server.tool()
    def build_key_door_scene(scene: Literal["key-door-assets"]) -> dict[str, JsonValue]:
        """Build the fixed GridWorld asset sample and export BLEND, GLB and PNG."""
        return build_assets(scene, "blender_key_door_scene.py", ASSETS)

    @server.tool()
    def build_iuno_avatar(scene: Literal["iuno-chibi"]) -> dict[str, JsonValue]:
        """Build the rigged Q-style Iuno avatar and six motion clips."""
        return build_assets(scene, "blender_iuno_avatar.py", IUNO_ASSETS)

    server.run(transport="streamable-http", host="127.0.0.1", port=MCP_PORT, json_response=True)


@app.get("/")
def page() -> FileResponse:
    return FileResponse(ROOT / "scripts/blender_mcp_demo.html")


def trace_event(method: str, state: str, started: float, detail: JsonValue) -> str:
    return (
        json.dumps(
            {
                "method": method,
                "state": state,
                "ms": round((perf_counter() - started) * 1000),
                "detail": detail,
            },
            ensure_ascii=False,
        )
        + "\n"
    )


async def build_trace() -> AsyncIterator[str]:
    started = perf_counter()
    method = "连接"
    yield trace_event(method, "request", started, {"endpoint": MCP_URL})
    try:
        async with Client(MCP_URL, read_timeout_seconds=130) as client:
            protocol_method = (
                "initialize" if client.session.initialize_result else "server/discover"
            )
            info = client.server_info
            yield trace_event(
                protocol_method,
                "ok",
                started,
                {
                    "server": info.name if info else None,
                    "protocol": client.session.protocol_version,
                },
            )

            method, started = "tools/list", perf_counter()
            yield trace_event(method, "request", started, {})
            tools = await client.list_tools()
            yield trace_event(method, "ok", started, {"tools": [tool.name for tool in tools.tools]})

            method, started = "tools/call", perf_counter()
            arguments: dict[str, JsonValue] = {"scene": "key-door-assets"}
            yield trace_event(method, "request", started, {"name": TOOL, "arguments": arguments})
            result = await client.call_tool(TOOL, arguments)
            if result.is_error or not isinstance(result.structured_content, dict):
                logger.warning("Blender MCP tool error: %s", result.content)
                yield trace_event(
                    method, "error", started, "Blender 工具返回错误，请查看服务日志。"
                )
                return
            payload = result.structured_content
            run_id = UUID(payload["run_id"])
            yield trace_event(
                method,
                "ok",
                started,
                {
                    "run_id": str(run_id),
                    "scene": payload["scene"],
                    "files": {name: f"/runs/{run_id}/{name}" for name in ASSETS},
                    "bytes": payload["bytes"],
                },
            )
    except Exception:
        logger.exception("Blender demo failed during %s", method)
        yield trace_event(method, "error", started, "调用失败，请检查 MCP 服务和本地日志。")


@app.post("/build")
def build(request: Request) -> StreamingResponse:
    if request.headers.get("X-Blender-Demo") != "build":
        raise HTTPException(status_code=403)
    return StreamingResponse(build_trace(), media_type="application/x-ndjson")


@app.get("/runs/{run_id}/{name}")
def asset(run_id: UUID, name: str) -> FileResponse:
    folder = DEMO / "runs" / str(run_id)
    if name not in (*ASSETS, *IUNO_ASSETS) or not (folder / "ready").is_file():
        raise HTTPException(status_code=404)
    path = folder / name
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, filename=None if path.suffix == ".png" else name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    mcp = subcommands.add_parser("mcp")
    mcp.add_argument("--blender", type=Path, required=True)
    subcommands.add_parser("web")
    args = parser.parse_args()
    if args.command == "mcp":
        if not args.blender.is_file():
            parser.error("--blender must point to the Blender executable")
        serve_mcp(args.blender.resolve())
    else:
        uvicorn.run(app, host="127.0.0.1", port=WEB_PORT)


if __name__ == "__main__":
    main()
