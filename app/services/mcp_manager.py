"""MCP manager — zip extraction, connection management, tool execution."""
import io
import os
import re
import uuid
import json
import shutil
import zipfile
import tempfile
import logging
from pathlib import Path
from contextlib import AsyncExitStack

import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types import Tool as MCPToolDef, TextContent

from app.config import get_settings
from app.models.mcp_server import MCPServer
from app.tools.base import ToolResult
from app.tools.mcp_tool import MCPToolWrapper

logger = logging.getLogger("mcp_manager")
settings = get_settings()


class MCPError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


class MCPSession:
    """Active MCP session: exit stack + client session."""

    def __init__(self, name: str):
        self.name = name
        self._exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, command: str, args: list[str], cwd: str):
        server_params = StdioServerParameters(command=command, args=args)
        transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = transport
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        self._connected = True

    async def disconnect(self):
        self._connected = False
        self.session = None
        await self._exit_stack.aclose()

    async def list_tools(self) -> list[MCPToolDef]:
        if not self.session or not self._connected:
            raise MCPError("MCP_NOT_CONNECTED", f"Server '{self.name}' not connected", 500)
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, arguments: dict) -> list[TextContent]:
        if not self.session or not self._connected:
            raise MCPError("MCP_NOT_CONNECTED", f"Server '{self.name}' not connected", 500)
        result = await self.session.call_tool(tool_name, arguments)
        return result.content


class MCPManager:
    """Singleton manager for MCP server lifecycle."""

    def __init__(self):
        self._sessions: dict[str, MCPSession] = {}

    # ---- Zip extraction (like create_skill_from_zip) ----

    def _find_mcp_md(self, folder: str) -> str:
        """Recursively find MCP.md in extracted folder (case-insensitive)."""
        for root, dirs, files in os.walk(folder):
            for f in files:
                if f.lower() == "mcp.md":
                    return os.path.join(root, f)
        raise MCPError("MCP_PARSE_ERROR", "ZIP 中未找到 MCP.md 文件")

    def _parse_mcp_md(self, filepath: str) -> tuple[str, str, str, list[str]]:
        """Parse MCP.md YAML frontmatter. Returns (name, description, command, args)."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not match:
            raise MCPError("MCP_PARSE_ERROR", "MCP.md 缺少 YAML 头 (--- ... ---)")

        try:
            data = yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            raise MCPError("MCP_PARSE_ERROR", f"MCP.md YAML 解析失败: {e}")

        if not data or not isinstance(data, dict):
            raise MCPError("MCP_PARSE_ERROR", "MCP.md YAML 头为空")

        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        command = (data.get("command") or "").strip()
        args = data.get("args") or []

        if not name:
            raise MCPError("MCP_PARSE_ERROR", "MCP.md 缺少必填字段: name")
        if not description:
            raise MCPError("MCP_PARSE_ERROR", "MCP.md 缺少必填字段: description")
        if not command:
            raise MCPError("MCP_PARSE_ERROR", "MCP.md 缺少必填字段: command")

        return name, description, command, args

    async def create_mcp_from_zip(
        self,
        db: AsyncSession,
        user_id: str,
        workspace_id: str | None,
        zip_bytes: bytes,
        source: str = "private",
    ) -> MCPServer:
        """Extract MCP zip, parse MCP.md, store files, create DB record."""

        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                # Security: prevent zip slip
                for member in zf.infolist():
                    target = os.path.realpath(os.path.join(tmpdir, member.filename))
                    if not target.startswith(os.path.realpath(tmpdir) + os.sep):
                        raise MCPError("MCP_PARSE_ERROR", "ZIP 包含非法路径")

                zf.extractall(tmpdir)

            mcp_md_path = self._find_mcp_md(tmpdir)
            name, description, command, args = self._parse_mcp_md(mcp_md_path)

            # Move to permanent storage
            server_id = str(uuid.uuid4())
            server_folder = os.path.join(settings.skills_storage_path, "mcp", server_id)
            os.makedirs(server_folder, exist_ok=True)

            for entry in os.listdir(tmpdir):
                src = os.path.join(tmpdir, entry)
                dst = os.path.join(server_folder, entry)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

        server = MCPServer(
            id=server_id,
            workspace_id=workspace_id if source == "private" else None,
            uploader_id=user_id,
            source=source,
            name=name,
            description=description,
            command=command,
            args=json.dumps(args),
            folder_path=server_folder,
            enabled=True,
        )
        db.add(server)
        await db.commit()
        await db.refresh(server)
        logger.info("MCP server '%s' created (source=%s)", name, source)
        return server

    # ---- Connection management ----

    def get_session(self, name: str) -> MCPSession | None:
        return self._sessions.get(name)

    def is_connected(self, name: str) -> bool:
        s = self._sessions.get(name)
        return s is not None and s.connected

    async def connect(self, server: MCPServer) -> MCPSession:
        """Connect to an MCP server by spawning its command as stdio subprocess."""
        logger.info("Connecting MCP server '%s': %s %s", server.name, server.command, server.args_list)
        session = MCPSession(server.name)
        try:
            await session.connect(server.command, server.args_list, server.folder_path)
            self._sessions[server.name] = session
            logger.info("MCP server '%s' connected", server.name)
            return session
        except Exception as e:
            logger.error("Failed to connect MCP server '%s': %s", server.name, e)
            await session.disconnect()
            raise MCPError("MCP_CONNECT_FAILED", f"连接 MCP 服务器失败: {e}", 500)

    async def disconnect(self, name: str):
        session = self._sessions.pop(name, None)
        if session:
            logger.info("Disconnecting MCP server '%s'", name)
            await session.disconnect()

    async def fetch_tools(self, server: MCPServer) -> list[MCPToolWrapper]:
        """Connect if needed, discover tools, return wrappers."""
        session = self._sessions.get(server.name)
        if not session or not session.connected:
            session = await self.connect(server)

        server_tools = await session.list_tools()
        wrappers = []
        for tool in server_tools:
            input_schema = tool.inputSchema if getattr(tool, 'inputSchema', None) else {}
            wrapper = MCPToolWrapper(
                server_name=server.name,
                tool_name=tool.name,
                tool_description=tool.description or "",
                input_schema=input_schema,
                call_tool=lambda tn, args, s=session: self._execute_tool(s, tn, args),
            )
            wrappers.append(wrapper)
        logger.info("MCP server '%s': %d tools discovered", server.name, len(wrappers))
        return wrappers

    async def _execute_tool(self, session: MCPSession, tool_name: str, args: dict) -> ToolResult:
        try:
            content_items = await session.call_tool(tool_name, args)
            parts = []
            for item in (content_items or []):
                if hasattr(item, 'text'):
                    parts.append(item.text)
                elif isinstance(item, dict):
                    parts.append(item.get("text", json.dumps(item, ensure_ascii=False)))
                else:
                    parts.append(str(item))
            return ToolResult(content="\n".join(parts))
        except Exception as e:
            logger.exception("MCP tool '%s' failed on '%s'", tool_name, session.name)
            return ToolResult(content=f"MCP tool error: {e}", is_error=True)

    async def delete_server(self, db: AsyncSession, server: MCPServer):
        """Delete server: disconnect, remove files, remove DB record."""
        await self.disconnect(server.name)
        if os.path.exists(server.folder_path):
            shutil.rmtree(server.folder_path)
        await db.delete(server)
        await db.commit()


# Singleton
mcp_manager = MCPManager()
