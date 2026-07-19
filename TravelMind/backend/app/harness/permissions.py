"""Return ALLOW, ASK, or DENY before every tool invocation."""

from enum import StrEnum


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"

