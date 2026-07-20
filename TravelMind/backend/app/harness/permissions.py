"""Return ALLOW, ASK, or DENY before every tool invocation."""

from enum import StrEnum


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class RiskLevel(StrEnum):
    """Impact level declared by a tool."""

    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"


class PermissionEngine:
    """Apply one predictable policy to local and MCP tools."""

    def decide(self, risk_level: RiskLevel, approved: bool = False) -> PermissionDecision:
        """Allow reads, require approval for writes, and deny dangerous actions."""
        if risk_level is RiskLevel.DANGEROUS:
            return PermissionDecision.DENY
        if risk_level is RiskLevel.WRITE and not approved:
            return PermissionDecision.ASK
        return PermissionDecision.ALLOW
