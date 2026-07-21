"""Check configured MCP servers without printing credentials."""

import asyncio

from app.config import settings
from app.mcp.config import MCPConfig
from app.mcp.manager import MCPManager


async def main() -> None:
    manager = MCPManager(MCPConfig.load(settings.mcp_config_path))
    await manager.start()
    try:
        print(
            {
                "connected": list(manager.sessions),
                "tool_count": len(manager.tools),
                "error_servers": list(manager.errors),
            }
        )
        print({"tools": list(manager.tools)[:20]})
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
