"""Convert discovered MCP tools to Harness ToolDefinitions."""

from typing import Any

from pydantic import BaseModel, Field, create_model

from app.harness.permissions import RiskLevel
from app.harness.tool_registry import ToolDefinition, ToolRegistry
from app.mcp.manager import MCPManager


def _python_type(schema: dict[str, Any]) -> Any:
    """Map the common JSON Schema primitives used by MCP tools."""
    return {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list[Any],
        "object": dict[str, Any],
    }.get(schema.get("type"), Any)


def model_from_json_schema(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic argument model from a basic MCP input schema."""
    required = set(schema.get("required", []))
    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, field_schema in schema.get("properties", {}).items():
        annotation = _python_type(field_schema)
        default = ... if field_name in required else None
        if default is None:
            annotation = annotation | None
        fields[field_name] = (
            annotation,
            Field(default=default, description=field_schema.get("description")),
        )
    return create_model(name, **fields)


def _risk_level(name: str) -> RiskLevel:
    lowered = name.lower()
    if any(action in lowered for action in ("create", "update", "delete", "send", "write")):
        return RiskLevel.WRITE
    return RiskLevel.READ


def register_mcp_tools(manager: MCPManager, registry: ToolRegistry) -> None:
    """Register all currently discovered remote tools in the shared registry."""
    for discovered in manager.tools.values():

        async def call_remote(
            _qualified_name: str = discovered.qualified_name,
            **arguments: Any,
        ) -> Any:
            result = await manager.call_tool(_qualified_name, arguments)
            structured = getattr(result, "structuredContent", None)
            if structured is not None:
                return structured
            return [
                getattr(block, "text", "")
                for block in getattr(result, "content", [])
                if getattr(block, "text", None)
            ]

        registry.register(
            ToolDefinition(
                name=discovered.qualified_name,
                description=discovered.description,
                args_model=model_from_json_schema(
                    f"{discovered.server}_{discovered.name}_Arguments",
                    discovered.input_schema,
                ),
                handler=call_remote,
                source=f"mcp:{discovered.server}",
                risk_level=_risk_level(discovered.name),
            )
        )
