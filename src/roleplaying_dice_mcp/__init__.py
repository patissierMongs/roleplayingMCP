"""MCP Dice Server — dice mechanics engine for AI-driven TRPG sessions.

The server rolls; the agent rules. This package provides fair random rolls
with raw structured results and a verifiable roll history. Game-system rules
(success, criticals, degrees, botches) are left to the calling agent.
"""

from .server import main

__all__ = ["main"]
