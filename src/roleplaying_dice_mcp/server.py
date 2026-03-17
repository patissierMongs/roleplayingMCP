"""
MCP Dice Server — slim transport layer.

Factor VII (Port Binding): Exports service via MCP stdio.
Factor VI (Stateless Processes): All state lives in injected DiceRoller.

This module is ONLY responsible for:
  1. Declaring MCP tool schemas
  2. Routing tool calls to DiceRoller
  3. Converting RollResult → CallToolResult
"""

import asyncio
import logging
import sys
from typing import Any

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import mcp.types as types

from .config import load_config
from .history import RollHistory
from .models import RollResult
from .roller import DiceRoller

# Factor XI (Logs): Treat logs as event streams → stdout
logging.basicConfig(
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("dice-server")


# ---------------------------------------------------------------------------
# Tool schema definitions (MCP transport concern only)
# ---------------------------------------------------------------------------

TOOLS = [
    types.Tool(
        name="roll_dice",
        description=(
            "Roll dice using standard TRPG notation. Supports modifiers, "
            "keep-highest/lowest, Fudge dice, advantage/disadvantage, "
            "bonus/penalty dice, target checks, degree calculations, "
            "and critical detection."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "notation": {
                    "type": "string",
                    "description": "Dice expression (NdM+X, NdFate, kh/kl).",
                },
                "advantage": {
                    "type": "boolean",
                    "description": "D&D 5e advantage (1d20 only).",
                    "default": False,
                },
                "disadvantage": {
                    "type": "boolean",
                    "description": "D&D 5e disadvantage (1d20 only).",
                    "default": False,
                },
                "bonus_dice": {
                    "type": "integer",
                    "description": "CoC bonus dice (1d100 only).",
                    "default": 0,
                    "minimum": 0,
                    "maximum": 2,
                },
                "penalty_dice": {
                    "type": "integer",
                    "description": "CoC penalty dice (1d100 only).",
                    "default": 0,
                    "minimum": 0,
                    "maximum": 2,
                },
                "target": {
                    "type": "integer",
                    "description": "DC, AC, or skill value for success check.",
                },
                "target_mode": {
                    "type": "string",
                    "enum": ["at_least", "at_most"],
                    "default": "at_least",
                },
                "critical": {
                    "type": "boolean",
                    "description": "Detect nat 20/1 on d20 rolls.",
                    "default": False,
                },
                "degrees": {
                    "type": "string",
                    "enum": ["coc", "pf2e", "pbta"],
                    "description": "Success degree system. Requires target (except pbta).",
                },
            },
            "required": ["notation"],
        },
    ),
    types.Tool(
        name="roll_pool",
        description=(
            "Roll a dice pool and count successes. "
            "Use for WoD, Shadowrun, or similar pool-based systems."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pool": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                },
                "sides": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 2,
                    "maximum": 100,
                },
                "target": {
                    "type": "integer",
                    "description": "Minimum value for a success.",
                    "default": 8,
                },
                "explode": {
                    "type": "boolean",
                    "description": "Reroll on max value.",
                    "default": False,
                },
                "double_on": {
                    "type": "integer",
                    "description": "Threshold for double successes (must be >= target).",
                },
                "count_ones": {
                    "type": "boolean",
                    "description": "Enable botch/glitch detection.",
                    "default": False,
                },
            },
            "required": ["pool"],
        },
    ),
    types.Tool(
        name="reroll",
        description="Re-roll the last roll with identical parameters.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_history",
        description="Retrieve recent roll history for this session.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
        },
    ),
    types.Tool(
        name="clear_history",
        description="Clear all roll history for this session.",
        inputSchema={"type": "object", "properties": {}},
    ),
]


# ---------------------------------------------------------------------------
# Server factory — Dependency Injection entry point
# ---------------------------------------------------------------------------

def create_server() -> tuple[Server, DiceRoller]:
    """Wire dependencies and return configured (Server, DiceRoller).

    Factor VI: Stateless process — all state in DiceRoller.
    Factor IV: History is an injected backing service.
    """
    config = load_config()
    logger.setLevel(config.log_level)

    history = RollHistory(max_size=config.history_max_size)
    roller = DiceRoller(config=config, history=history)
    server = Server(config.name)

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return TOOLS

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None,
    ) -> types.CallToolResult:
        args = arguments or {}
        result = _dispatch(roller, name, args)
        return _to_mcp_result(result)

    return server, roller


def _dispatch(roller: DiceRoller, name: str, args: dict[str, Any]) -> RollResult:
    """Route MCP tool call to the appropriate DiceRoller method."""
    if name == "roll_dice":
        notation = args.get("notation")
        if not notation:
            return RollResult.error("'notation' parameter is required.")
        target_mode = args.get("target_mode", "at_least")
        if target_mode not in ("at_least", "at_most"):
            return RollResult.error("'target_mode' must be 'at_least' or 'at_most'.")
        return roller.roll_dice(
            notation=notation,
            advantage=bool(args.get("advantage", False)),
            disadvantage=bool(args.get("disadvantage", False)),
            bonus_dice=int(args.get("bonus_dice", 0)),
            penalty_dice=int(args.get("penalty_dice", 0)),
            target=args.get("target"),
            target_mode=target_mode,
            critical=bool(args.get("critical", False)),
            degrees=args.get("degrees"),
        )

    elif name == "roll_pool":
        pool = args.get("pool")
        if pool is None:
            return RollResult.error("'pool' parameter is required.")
        return roller.roll_pool(
            pool=int(pool),
            sides=int(args.get("sides", 10)),
            target=int(args.get("target", 8)),
            explode=bool(args.get("explode", False)),
            double_on=(
                int(args["double_on"])
                if args.get("double_on") is not None
                else None
            ),
            count_ones=bool(args.get("count_ones", False)),
        )

    elif name == "reroll":
        return roller.reroll()

    elif name == "get_history":
        return roller.get_history(limit=int(args.get("limit", 10)))

    elif name == "clear_history":
        return roller.clear_history()

    else:
        return RollResult.error(f"Unknown tool: '{name}'")


def _to_mcp_result(result: RollResult) -> types.CallToolResult:
    """Convert domain RollResult to MCP CallToolResult."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=result.text)],
        isError=result.is_error,
    )


# ---------------------------------------------------------------------------
# Entry point — Factor IX (Disposability): fast startup
# ---------------------------------------------------------------------------

async def _run():
    server, _ = create_server()
    config = load_config()
    logger.info("Starting %s v%s", config.name, config.version)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=config.name,
                server_version=config.version,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main():
    """Entry point for the CLI command."""
    asyncio.run(_run())
