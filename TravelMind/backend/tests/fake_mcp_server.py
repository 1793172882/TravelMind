"""Small official MCP stdio Server used by integration tests and demos."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("travelmind-demo")


@mcp.tool()
def echo(text: str) -> str:
    """Return text unchanged."""
    return text


@mcp.tool()
def create_note(title: str) -> dict[str, str]:
    """Simulate an external write that must pass Harness approval."""
    return {"status": "created", "title": title}


if __name__ == "__main__":
    mcp.run(transport="stdio")
