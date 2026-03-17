"""
Shared data models for the dice server.

Decouples roll results from MCP transport types,
enabling testability and reuse across different interfaces.
"""

from dataclasses import dataclass, field


@dataclass
class RollResult:
    """Unified result from any roll operation."""

    lines: list[str] = field(default_factory=list)
    is_error: bool = False

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @staticmethod
    def error(message: str) -> "RollResult":
        return RollResult(lines=[f"Error: {message}"], is_error=True)

    @staticmethod
    def ok(lines: list[str]) -> "RollResult":
        return RollResult(lines=lines, is_error=False)
