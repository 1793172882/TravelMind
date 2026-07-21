"""Check configured MCP servers without printing credentials."""

import argparse
import asyncio
import json

from app.config import settings
from app.mcp.config import MCPConfig
from app.mcp.manager import MCPManager


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schemas", action="store_true")
    arguments = parser.parse_args()
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
        if arguments.schemas:
            print(
                json.dumps(
                    {
                        name: tool.input_schema
                        for name, tool in manager.tools.items()
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
