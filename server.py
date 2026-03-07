#!/usr/bin/env python3
"""
MCP Dice Server — TRPG-ready dice rolling server using Model Context Protocol.

Tools:
  - roll_dice  : Standard dice notation (NdM+K) with advantage/disadvantage
  - roll_pool  : Dice pool with success counting (WoD, Shadowrun, etc.)
  - get_history: Retrieve recent roll history
  - clear_history: Clear roll history
"""

import asyncio
import random
from typing import Any

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import mcp.types as types

from dice_parser import parse, ParsedNotation, DiceGroup
from history import RollHistory

server = Server("dice-server")
history = RollHistory(max_size=100)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    types.Tool(
        name="roll_dice",
        description=(
            "Roll dice using standard TRPG notation (e.g. '2d6+3', '1d20+5', '4d6', '1d100'). "
            "Supports advantage/disadvantage for d20 rolls. "
            "Returns individual rolls and the total."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "notation": {
                    "type": "string",
                    "description": (
                        "Dice notation string. Examples: '1d20+5', '2d6+3', "
                        "'4d6', '1d100', '3d20-2d20+2' (compound with negative dice)."
                    ),
                },
                "advantage": {
                    "type": "string",
                    "enum": ["normal", "advantage", "disadvantage"],
                    "description": (
                        "Roll mode for the primary d20 roll. "
                        "'advantage': roll twice, take higher. "
                        "'disadvantage': roll twice, take lower. "
                        "Only applies when the notation contains a single d20 group."
                    ),
                    "default": "normal",
                },
                "target": {
                    "type": "integer",
                    "description": (
                        "Optional target number (DC/AC). If provided, the result "
                        "will indicate success or failure."
                    ),
                },
            },
            "required": ["notation"],
        },
    ),
    types.Tool(
        name="roll_pool",
        description=(
            "Roll a dice pool and count successes. Used for systems like "
            "World of Darkness, Shadowrun, etc. Roll N dice, count how many "
            "meet or exceed the target number."
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
                    "description": "Number of sides per die. Default: 10.",
                    "default": 10,
                    "minimum": 2,
                    "maximum": 100,
                },
                "target": {
                    "type": "integer",
                    "description": "Minimum value for a success. Default: 8.",
                    "default": 8,
                },
                "explode": {
                    "type": "boolean",
                    "description": (
                        "If true, dice that roll the maximum value are rolled again "
                        "(exploding dice). Default: false."
                    ),
                    "default": False,
                },
                "double_on": {
                    "type": "integer",
                    "description": (
                        "Optional. Rolls at or above this value count as 2 successes "
                        "instead of 1. Must be >= target."
                    ),
                },
            },
            "required": ["pool"],
        },
    ),
    types.Tool(
        name="get_history",
        description="Retrieve recent dice roll history for the current session.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent rolls to retrieve. Default: 10.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
        },
    ),
    types.Tool(
        name="clear_history",
        description="Clear all dice roll history for the current session.",
        inputSchema={"type": "object", "properties": {}},
    ),
]


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return TOOLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_error(message: str) -> list[types.TextContent]:
    """Return an MCP-compliant error response as TextContent with isError flag."""
    return [types.TextContent(type="text", text=f"Error: {message}")]


def _roll_group(group: DiceGroup) -> list[int]:
    """Roll all dice in a group, return list of results."""
    return [random.randint(1, group.sides) for _ in range(group.count)]


# ---------------------------------------------------------------------------
# roll_dice implementation
# ---------------------------------------------------------------------------

def _execute_roll_dice(
    notation: str,
    advantage: str = "normal",
    target: int | None = None,
) -> tuple[str, bool]:
    """Execute a dice roll. Returns (result_text, is_error)."""
    try:
        parsed = parse(notation)
    except ValueError as e:
        return str(e), True

    # Advantage/disadvantage: only valid for single d20 group
    adv_applicable = (
        advantage != "normal"
        and len(parsed.groups) == 1
        and parsed.groups[0].sides == 20
        and parsed.groups[0].count == 1
        and not parsed.groups[0].negative
    )

    if advantage != "normal" and not adv_applicable:
        return (
            "어드밴티지/디스어드밴티지는 단일 1d20 굴림에만 적용 가능합니다. "
            f"현재 표현식: '{notation}'"
        ), True

    lines: list[str] = []

    if adv_applicable:
        # Roll twice
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        if advantage == "advantage":
            chosen = max(roll1, roll2)
            label = "Advantage"
        else:
            chosen = min(roll1, roll2)
            label = "Disadvantage"

        total = chosen + parsed.modifier
        lines.append(f"Roll ({label}): 1d20 → [{roll1}, {roll2}] → 선택: {chosen}")
        if parsed.modifier != 0:
            sign = "+" if parsed.modifier > 0 else ""
            lines.append(f"Modifier: {sign}{parsed.modifier}")
        lines.append(f"Total: {total}")
    else:
        # Standard roll
        all_results: list[tuple[DiceGroup, list[int]]] = []
        for group in parsed.groups:
            rolls = _roll_group(group)
            all_results.append((group, rolls))

        # Build output
        positive_sum = 0
        negative_sum = 0

        for group, rolls in all_results:
            prefix = "-" if group.negative else ""
            rolls_str = ", ".join(str(r) for r in rolls)
            lines.append(f"{prefix}{group.count}d{group.sides}: [{rolls_str}]")
            if group.negative:
                negative_sum += sum(rolls)
            else:
                positive_sum += sum(rolls)

        dice_total = positive_sum - negative_sum
        total = dice_total + parsed.modifier

        if parsed.modifier != 0:
            sign = "+" if parsed.modifier > 0 else ""
            lines.append(f"Modifier: {sign}{parsed.modifier}")

        if negative_sum > 0:
            lines.append(f"Total: {positive_sum} - {negative_sum} {'+' if parsed.modifier >= 0 else ''}{parsed.modifier if parsed.modifier != 0 else ''} = {total}".rstrip(" ="))
            # Clean up the total line
            lines[-1] = f"Total: {positive_sum} - {negative_sum}"
            if parsed.modifier != 0:
                sign = "+" if parsed.modifier > 0 else ""
                lines[-1] += f" {sign}{parsed.modifier}"
            lines[-1] += f" = {total}"
        else:
            lines.append(f"Total: {total}")

    # Target check
    if target is not None:
        if total >= target:
            lines.append(f"판정: 성공! ({total} ≥ {target})")
        else:
            lines.append(f"판정: 실패 ({total} < {target})")

    return "\n".join(lines), False


# ---------------------------------------------------------------------------
# roll_pool implementation
# ---------------------------------------------------------------------------

def _execute_roll_pool(
    pool: int,
    sides: int = 10,
    target: int = 8,
    explode: bool = False,
    double_on: int | None = None,
) -> tuple[str, bool]:
    """Execute a dice pool roll. Returns (result_text, is_error)."""
    if pool < 1 or pool > 50:
        return "다이스 풀 크기는 1~50 사이여야 합니다.", True
    if sides < 2:
        return "주사위 면 수는 2 이상이어야 합니다.", True
    if target < 1 or target > sides:
        return f"성공 기준값은 1~{sides} 사이여야 합니다.", True
    if double_on is not None and double_on < target:
        return f"double_on({double_on})은 target({target}) 이상이어야 합니다.", True

    rolls: list[str] = []  # display strings
    successes = 0

    for _ in range(pool):
        roll = random.randint(1, sides)
        chain = [roll]

        # Exploding dice
        while explode and chain[-1] == sides:
            chain.append(random.randint(1, sides))

        # Count successes from chain
        die_successes = 0
        for val in chain:
            if val >= target:
                if double_on is not None and val >= double_on:
                    die_successes += 2
                else:
                    die_successes += 1

        successes += die_successes

        # Format display
        if len(chain) > 1:
            chain_str = "→".join(str(v) for v in chain)
            rolls.append(f"({chain_str})")
        else:
            rolls.append(str(roll))

    lines: list[str] = []
    lines.append(f"Dice Pool: {pool}d{sides} (target ≥ {target}"
                 + (", exploding" if explode else "")
                 + (f", double on ≥ {double_on}" if double_on else "")
                 + ")")
    lines.append(f"Rolls: [{', '.join(rolls)}]")
    lines.append(f"Successes: {successes}")

    return "\n".join(lines), False


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    args = arguments or {}

    if name == "roll_dice":
        notation = args.get("notation")
        if not notation:
            return _make_error("'notation' 파라미터가 필요합니다. 예: '1d20+5'")
        advantage = args.get("advantage", "normal")
        if advantage not in ("normal", "advantage", "disadvantage"):
            return _make_error("'advantage'는 'normal', 'advantage', 'disadvantage' 중 하나여야 합니다.")
        target = args.get("target")

        text, is_error = _execute_roll_dice(notation, advantage, target)

        if not is_error:
            history.add("roll_dice", f"{notation}" + (f" ({advantage})" if advantage != "normal" else ""), text)

        return [types.TextContent(type="text", text=text)]

    elif name == "roll_pool":
        pool = args.get("pool")
        if pool is None:
            return _make_error("'pool' 파라미터가 필요합니다.")

        text, is_error = _execute_roll_pool(
            pool=int(pool),
            sides=int(args.get("sides", 10)),
            target=int(args.get("target", 8)),
            explode=bool(args.get("explode", False)),
            double_on=int(args["double_on"]) if args.get("double_on") is not None else None,
        )

        if not is_error:
            desc = f"{pool}d{args.get('sides', 10)} pool (target≥{args.get('target', 8)})"
            history.add("roll_pool", desc, text)

        return [types.TextContent(type="text", text=text)]

    elif name == "get_history":
        limit = int(args.get("limit", 10))
        records = history.get(limit)
        if not records:
            return [types.TextContent(type="text", text="굴림 기록이 없습니다.")]

        lines = [f"=== 최근 {len(records)}개 굴림 기록 ==="]
        for i, rec in enumerate(records, 1):
            lines.append(f"[{i}] ({rec.timestamp}) {rec.tool}: {rec.input_desc}")
            lines.append(f"    → {rec.result_text.split(chr(10))[-1]}")  # last line (Total/Successes)
        return [types.TextContent(type="text", text="\n".join(lines))]

    elif name == "clear_history":
        count = history.clear()
        return [types.TextContent(type="text", text=f"굴림 기록 {count}건을 삭제했습니다.")]

    else:
        return _make_error(f"알 수 없는 tool입니다: '{name}'")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="dice-server",
                server_version="2.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
