#!/usr/bin/env python3
"""
MCP Dice Server — a dice *mechanics* engine for AI-driven TRPG sessions.

Scope: this server produces fair random rolls and returns raw, structured
results as JSON. It deliberately contains no game-system rules —
success/failure, criticals, degrees of success, botches and glitches are
judgments the calling agent makes from the returned values.

Tools:
  - roll_dice    : Standard dice notation (NdM+X, kh/kl, dF, compound),
                   plus CoC-style bonus/penalty tens dice for 1d100
  - roll_pool    : Dice pool — success counting, exploding dice, raw 1s count
  - reroll       : Re-roll the last roll with identical parameters
  - get_history  : Retrieve recent roll history
  - clear_history: Clear roll history
"""

import asyncio
import json
import random
from typing import Any

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import mcp.types as types

from .dice_parser import parse, DiceGroup, ParsedNotation
from .history import RollHistory

server = Server("dice-server")
history = RollHistory(max_size=100)
_last_roll: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    types.Tool(
        name="roll_dice",
        description=(
            "Roll dice using standard TRPG notation and return raw structured "
            "results as JSON. Supports modifiers (2d6+3), compound groups "
            "(2d6+1d4+1), keep-highest/lowest (4d6kh3, 2d20kl1), Fudge/FATE "
            "dice (4dF), and CoC-style bonus/penalty tens dice for 1d100. "
            "The server only rolls — apply game-system rules (success/failure, "
            "criticals, degrees of success) yourself from the returned values. "
            "Common idioms: D&D advantage = '2d20kh1+MOD', "
            "disadvantage = '2d20kl1+MOD'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "notation": {
                    "type": "string",
                    "description": (
                        "Dice expression: NdM, NdM+X, khN/klN suffix, dF for "
                        "Fudge dice, compound groups joined with +/-."
                    ),
                },
                "bonus_dice": {
                    "type": "integer",
                    "description": (
                        "CoC-style bonus tens dice (1d100 only): roll extra "
                        "tens dice sharing one units die, keep the lowest result."
                    ),
                    "default": 0,
                    "minimum": 0,
                    "maximum": 2,
                },
                "penalty_dice": {
                    "type": "integer",
                    "description": (
                        "CoC-style penalty tens dice (1d100 only): roll extra "
                        "tens dice sharing one units die, keep the highest result."
                    ),
                    "default": 0,
                    "minimum": 0,
                    "maximum": 2,
                },
            },
            "required": ["notation"],
        },
    ),
    types.Tool(
        name="roll_pool",
        description=(
            "Roll a pool of dice and count successes against a threshold. "
            "Returns raw JSON: per-die roll chains (exploding rerolls appear "
            "in the chain), total successes, and the count of 1s. Use for "
            "pool-based systems (WoD, Shadowrun). Judge botch/glitch rules "
            "yourself from 'successes' and 'ones'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pool": {
                    "type": "integer",
                    "description": "Number of dice to roll.",
                    "minimum": 1,
                    "maximum": 50,
                },
                "sides": {
                    "type": "integer",
                    "description": "Sides per die.",
                    "default": 10,
                    "minimum": 2,
                    "maximum": 100,
                },
                "target": {
                    "type": "integer",
                    "description": "Minimum value that counts as one success (>=).",
                    "default": 8,
                },
                "explode": {
                    "type": "boolean",
                    "description": "Reroll on max value; rerolls extend the die's chain.",
                    "default": False,
                },
                "double_on": {
                    "type": "integer",
                    "description": (
                        "Values at or above this count as two successes "
                        "(must be >= target)."
                    ),
                },
            },
            "required": ["pool"],
        },
    ),
    types.Tool(
        name="reroll",
        description=(
            "Re-roll the last roll_dice or roll_pool with identical parameters "
            "and return fresh results (marked \"reroll\": true)."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_history",
        description=(
            "Retrieve recent roll history for this session as a JSON array "
            "(most recent first)."
        ),
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


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return TOOLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"Error: {message}")],
        isError=True,
    )


def _ok_json(payload: dict[str, Any] | list[Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(
            type="text", text=json.dumps(payload, ensure_ascii=False),
        )],
        isError=False,
    )


def _roll_group(group: DiceGroup) -> list[int]:
    if group.fudge:
        return [random.choice([-1, 0, 1]) for _ in range(group.count)]
    return [random.randint(1, group.sides) for _ in range(group.count)]


def _apply_keep(rolls: list[int], group: DiceGroup) -> tuple[list[int], list[int]]:
    if group.keep_highest is not None:
        sorted_rolls = sorted(enumerate(rolls), key=lambda x: x[1], reverse=True)
        kept_indices = {idx for idx, _ in sorted_rolls[:group.keep_highest]}
    elif group.keep_lowest is not None:
        sorted_rolls = sorted(enumerate(rolls), key=lambda x: x[1])
        kept_indices = {idx for idx, _ in sorted_rolls[:group.keep_lowest]}
    else:
        return rolls, []
    kept = [r for i, r in enumerate(rolls) if i in kept_indices]
    dropped = [r for i, r in enumerate(rolls) if i not in kept_indices]
    return kept, dropped


def _group_label(group: DiceGroup) -> str:
    sides = "F" if group.fudge else str(group.sides)
    label = f"{group.count}d{sides}"
    if group.keep_highest is not None:
        label += f"kh{group.keep_highest}"
    elif group.keep_lowest is not None:
        label += f"kl{group.keep_lowest}"
    return label


# ---------------------------------------------------------------------------
# roll_dice implementation
# ---------------------------------------------------------------------------

def _execute_roll_dice(
    notation: str,
    bonus_dice: int = 0,
    penalty_dice: int = 0,
) -> types.CallToolResult:
    if bonus_dice > 0 and penalty_dice > 0:
        return _error_result("Cannot use both bonus_dice and penalty_dice.")

    try:
        parsed = parse(notation)
    except ValueError as e:
        return _error_result(str(e))

    if bonus_dice > 0 or penalty_dice > 0:
        group = parsed.groups[0]
        bp_applicable = (
            len(parsed.groups) == 1
            and group.sides == 100
            and group.count == 1
            and not group.negative
            and not group.fudge
            and group.keep_highest is None
            and group.keep_lowest is None
        )
        if not bp_applicable:
            return _error_result(
                f"Bonus/penalty dice only apply to a single 1d100 roll. "
                f"Got: '{notation}'"
            )
        return _roll_percentile_with_bp(parsed, bonus_dice, penalty_dice)

    groups_payload: list[dict[str, Any]] = []
    total = parsed.modifier
    for group in parsed.groups:
        rolls = _roll_group(group)
        kept, dropped = _apply_keep(rolls, group)
        subtotal = -sum(kept) if group.negative else sum(kept)
        total += subtotal
        groups_payload.append({
            "dice": _group_label(group),
            "negative": group.negative,
            "rolls": rolls,
            "kept": kept,
            "dropped": dropped,
            "subtotal": subtotal,
        })

    payload = {
        "notation": parsed.original,
        "groups": groups_payload,
        "modifier": parsed.modifier,
        "total": total,
    }
    history.add("roll_dice", notation, f"total {total}")
    return _ok_json(payload)


def _roll_percentile_with_bp(
    parsed: ParsedNotation, bonus_dice: int, penalty_dice: int,
) -> types.CallToolResult:
    """Roll 1d100 with CoC-style bonus/penalty tens dice.

    All tens dice share a single units die; bonus keeps the lowest
    candidate, penalty keeps the highest. A 00 tens + 0 units reads as 100.
    """
    units = random.randint(0, 9)
    num_tens = 1 + bonus_dice + penalty_dice
    tens_rolls = [random.randint(0, 9) for _ in range(num_tens)]

    candidates = []
    for t in tens_rolls:
        value = t * 10 + units
        candidates.append(100 if value == 0 else value)

    result = min(candidates) if bonus_dice > 0 else max(candidates)
    total = result + parsed.modifier

    payload = {
        "notation": parsed.original,
        "bonus_dice": bonus_dice,
        "penalty_dice": penalty_dice,
        "units_die": units,
        "tens_dice": tens_rolls,
        "candidates": candidates,
        "result": result,
        "modifier": parsed.modifier,
        "total": total,
    }
    bp_label = f"bonus×{bonus_dice}" if bonus_dice > 0 else f"penalty×{penalty_dice}"
    history.add("roll_dice", f"{parsed.original} ({bp_label})", f"total {total}")
    return _ok_json(payload)


# ---------------------------------------------------------------------------
# roll_pool implementation
# ---------------------------------------------------------------------------

def _execute_roll_pool(
    pool: int,
    sides: int = 10,
    target: int = 8,
    explode: bool = False,
    double_on: int | None = None,
) -> types.CallToolResult:
    if pool < 1 or pool > 50:
        return _error_result("Pool size must be between 1 and 50.")
    if sides < 2:
        return _error_result("Sides must be at least 2.")
    if target < 1 or target > sides:
        return _error_result(f"Target must be between 1 and {sides}.")
    if double_on is not None and double_on < target:
        return _error_result(f"double_on ({double_on}) must be >= target ({target}).")

    chains: list[list[int]] = []
    successes = 0
    ones = 0
    dice_rolled = 0

    for _ in range(pool):
        chain = [random.randint(1, sides)]
        while explode and chain[-1] == sides:
            chain.append(random.randint(1, sides))

        for val in chain:
            if val >= target:
                if double_on is not None and val >= double_on:
                    successes += 2
                else:
                    successes += 1
            if val == 1:
                ones += 1

        dice_rolled += len(chain)
        chains.append(chain)

    payload = {
        "pool": pool,
        "sides": sides,
        "target": target,
        "explode": explode,
        "double_on": double_on,
        "dice": chains,
        "successes": successes,
        "ones": ones,
        "dice_rolled": dice_rolled,
    }
    history.add(
        "roll_pool",
        f"{pool}d{sides} (target>={target})",
        f"{successes} successes, {ones} ones",
    )
    return _ok_json(payload)


# ---------------------------------------------------------------------------
# Roll dispatcher (supports reroll via stored params)
# ---------------------------------------------------------------------------

def _dispatch_roll(name: str, args: dict[str, Any]) -> types.CallToolResult:
    global _last_roll

    if name == "roll_dice":
        notation = args.get("notation")
        if not notation:
            return _error_result("'notation' parameter is required.")

        _last_roll = {"tool": name, "args": dict(args)}
        return _execute_roll_dice(
            notation,
            bonus_dice=int(args.get("bonus_dice", 0)),
            penalty_dice=int(args.get("penalty_dice", 0)),
        )

    elif name == "roll_pool":
        pool = args.get("pool")
        if pool is None:
            return _error_result("'pool' parameter is required.")

        _last_roll = {"tool": name, "args": dict(args)}
        return _execute_roll_pool(
            pool=int(pool),
            sides=int(args.get("sides", 10)),
            target=int(args.get("target", 8)),
            explode=bool(args.get("explode", False)),
            double_on=(
                int(args["double_on"])
                if args.get("double_on") is not None
                else None
            ),
        )

    return _error_result(f"Unknown tool: '{name}'")


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None,
) -> types.CallToolResult:
    args = arguments or {}

    if name in ("roll_dice", "roll_pool"):
        return _dispatch_roll(name, args)

    elif name == "reroll":
        if _last_roll is None:
            return _error_result("No previous roll. Use roll_dice or roll_pool first.")
        result = _dispatch_roll(_last_roll["tool"], _last_roll["args"])
        if not result.isError:
            payload = json.loads(result.content[0].text)
            payload["reroll"] = True
            result = _ok_json(payload)
            records = history.get(1)
            if records:
                records[0].input_desc += " (reroll)"
        return result

    elif name == "get_history":
        limit = int(args.get("limit", 10))
        records = history.get(limit)
        payload = [
            {
                "timestamp": rec.timestamp,
                "tool": rec.tool,
                "input": rec.input_desc,
                "result": rec.result_text,
            }
            for rec in records
        ]
        return _ok_json(payload)

    elif name == "clear_history":
        count = history.clear()
        return _ok_json({"cleared": count})

    else:
        return _error_result(f"Unknown tool: '{name}'")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _run():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="dice-server",
                server_version="5.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main():
    """Entry point for the CLI command"""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
