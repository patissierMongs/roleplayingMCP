"""
Roll history — in-memory backing service.

Factor IV (Backing Services): History is treated as an attached resource.
The HistoryBackend protocol in roller.py defines the contract;
this module provides the default in-memory implementation.

Swap to Redis/SQLite/etc. by implementing the same protocol.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class RollRecord:
    """A single roll record."""
    timestamp: str
    tool: str
    input_desc: str
    result_text: str


class RollHistory:
    """In-memory roll history with a max capacity (FIFO eviction)."""

    def __init__(self, max_size: int = 100):
        self._records: list[RollRecord] = []
        self._max_size = max_size

    def add(self, tool: str, input_desc: str, result_text: str) -> None:
        record = RollRecord(
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            tool=tool,
            input_desc=input_desc,
            result_text=result_text,
        )
        self._records.append(record)
        if len(self._records) > self._max_size:
            self._records = self._records[-self._max_size:]

    def get(self, limit: int = 10) -> list[RollRecord]:
        return list(reversed(self._records[-limit:]))

    def clear(self) -> int:
        count = len(self._records)
        self._records.clear()
        return count

    @property
    def count(self) -> int:
        return len(self._records)
