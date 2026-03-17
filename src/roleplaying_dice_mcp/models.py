"""
Shared data models for the dice server.

Decouples roll results from MCP transport types,
enabling testability and reuse across different interfaces.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RollRecord:
    """A single roll record — shared between history backends."""
    timestamp: str
    tool: str
    input_desc: str
    result_text: str


@dataclass
class RollResult:
    """Unified result from any roll operation."""

    lines: list[str] = field(default_factory=list)
    is_error: bool = False
    total: int = 0
    natural_value: int | None = None

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @staticmethod
    def error(message: str) -> "RollResult":
        return RollResult(lines=[f"Error: {message}"], is_error=True)

    @staticmethod
    def ok(lines: list[str], total: int = 0, natural_value: int | None = None) -> "RollResult":
        return RollResult(lines=lines, is_error=False, total=total, natural_value=natural_value)
