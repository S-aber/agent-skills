"""Standalone MCP server for Wren Semantic Engine.

Wraps WrenEngine as MCP tools via FastMCP. Reads manifest from CLI arg,
connection info from environment variables.

Prerequisites:
    pip install wren-engine mcp

Environment variables:
    WREN_DATA_SOURCE   — required, e.g. postgres, duckdb
    WREN_HOST          — database host (for postgres etc.)
    WREN_PORT          — database port
    WREN_DATABASE      — database name
    WREN_USER          — database user
    WREN_PASSWORD      — database password
    WREN_FUNCTION_PATH — optional path to CSV of custom function definitions

Usage:
    python server.py --manifest manifest/mdl.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def _ensure_wren() -> None:
    try:
        from wren.engine import WrenEngine  # noqa: F401
        from wren.model.data_source import DataSource  # noqa: F401
    except ImportError:
        print(
            "Error: wren-engine not installed. Run: pip install wren-engine",
            file=sys.stderr,
        )
        sys.exit(1)


def _load_manifest(manifest_path: str) -> tuple[str, dict[str, Any]]:
    path = Path(manifest_path).expanduser()
    if not path.is_file():
        print(f"Error: manifest not found: {path}", file=sys.stderr)
        sys.exit(1)
    raw = path.read_bytes()
    manifest_str = base64.b64encode(raw).decode()
    manifest_json = json.loads(raw)
    return manifest_str, manifest_json


def _load_connection_info() -> tuple[str, dict[str, Any]]:
    ds = os.getenv("WREN_DATA_SOURCE")
    if not ds:
        print("Error: WREN_DATA_SOURCE env var is required.", file=sys.stderr)
        sys.exit(1)

    info: dict[str, Any] = {}
    host = os.getenv("WREN_HOST")
    port = os.getenv("WREN_PORT")
    database = os.getenv("WREN_DATABASE")
    user = os.getenv("WREN_USER")
    password = os.getenv("WREN_PASSWORD")

    if host:
        info["host"] = host
    if port:
        info["port"] = int(port)
    if database:
        info["database"] = database
    if user:
        info["user"] = user
    if password:
        info["password"] = password

    if not info:
        print(
            "Error: no connection info. Set WREN_HOST/WREN_PORT/WREN_DATABASE/WREN_USER/WREN_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)

    return ds, info


def _build_models_index(manifest_json: dict) -> dict[str, list[dict[str, Any]]]:
    models: dict[str, list[dict[str, Any]]] = {}
    for m in manifest_json.get("models", []):
        cols = []
        for c in m.get("columns", []):
            cols.append({
                "name": c["name"],
                "type": c.get("type", "unknown"),
                "description": c.get("description", ""),
            })
        models[m["name"]] = cols
    return models


def create_server(manifest_path: str) -> FastMCP:
    _ensure_wren()
    from wren.engine import WrenEngine
    from wren.model.data_source import DataSource

    manifest_str, manifest_json = _load_manifest(manifest_path)
    models_index = _build_models_index(manifest_json)
    data_source, connection_info = _load_connection_info()
    function_path = os.getenv("WREN_FUNCTION_PATH")

    engine = WrenEngine(
        manifest_str=manifest_str,
        data_source=DataSource(data_source),
        connection_info=connection_info,
        function_path=function_path,
    )

    mcp = FastMCP(
        name="wren",
        instructions="Wren Semantic Engine — query your data through the MDL semantic layer.",
    )

    @mcp.tool(
        name="wren_query",
        description="Execute a SQL query through the Wren semantic layer. "
        "Table references resolve to MDL models. Returns results as text table.",
    )
    def wren_query(sql: str, limit: int | None = None) -> str:
        result = engine.query(sql, limit=limit)
        df = result.to_pandas()
        return df.to_string(index=False)

    @mcp.tool(
        name="wren_dry_plan",
        description="Expand SQL through the semantic layer without executing. "
        "Returns the generated SQL with model CTEs. Useful for verifying "
        "how model references are resolved before running a query.",
    )
    def wren_dry_plan(sql: str) -> str:
        return engine.dry_plan(sql)

    @mcp.tool(
        name="wren_list_models",
        description="List all available models and their column counts from the MDL manifest.",
    )
    def wren_list_models() -> str:
        lines: list[str] = []
        for model_name, cols in models_index.items():
            lines.append(f"- {model_name} ({len(cols)} columns)")
        if not lines:
            return "No models found in manifest."
        return "\n".join(lines)

    @mcp.tool(
        name="wren_describe_model",
        description="Describe a specific model: its columns, types, and descriptions.",
    )
    def wren_describe_model(model_name: str) -> str:
        cols = models_index.get(model_name)
        if cols is None:
            available = ", ".join(models_index.keys()) or "(none)"
            return f"Model '{model_name}' not found. Available models: {available}"
        lines = [f"# {model_name}"]
        for c in cols:
            desc = f" — {c['description']}" if c["description"] else ""
            lines.append(f"  - {c['name']} ({c['type']}){desc}")
        return "\n".join(lines)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wren-mcp-server",
        description="Wren MCP Server for AI Agent Skills Workspace",
    )
    parser.add_argument(
        "--manifest", "-m",
        required=True,
        help="Path to MDL JSON manifest file",
    )
    args = parser.parse_args()

    server = create_server(args.manifest)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
