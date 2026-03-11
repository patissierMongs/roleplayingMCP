#!/usr/bin/env python3
"""
MCP Dice Server — TRPG-ready dice rolling server using Model Context Protocol.

Tools:
  - roll_dice  : Standard dice notation (NdM+K) with advantage/disadvantage,
                  keep highest/lowest, critical detection, target mode
  - roll_pool  : Dice pool with success counting (WoD, Shadowrun, etc.)
                  with optional botch/glitch detection
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

from .dice_parser import parse, DiceGroup
from .history import RollHistory

server = Server("dice-server")
history = RollHistory(max_size=100)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    types.Tool(
        name="roll_dice",
        description=(
            "Roll dice using standard TRPG notation (e.g. '2d6+3', '1d20+5', '4d6kh3'). "
            "Supports advantage/disadvantage, keep highest/lowest, "
            "critical hit/fumble detection, and flexible target comparison. "
            "Returns individual rolls and the total."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "notation": {
                    "type": "string",
                    "description": (
                        "Dice notation string. Examples: '1d20+5', '2d6+3', "
                        "'4d6kh3' (roll 4d6, keep highest 3), "
                        "'2d20kl1' (roll 2d20, keep lowest 1), "
                        "'3d20-2d20+2' (compound with negative dice)."
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
                        "Optional target number (DC/AC/skill value). "
                        "Combined with target_mode for success check."
                    ),
                },
                "target_mode": {
                    "type": "string",
                    "enum": ["at_least", "at_most"],
                    "description": (
                        "How to compare the result against the target. "
                        "'at_least' (default): success if result >= target (D&D style). "
                        "'at_most': success if result <= target (CoC/BRP style)."
                    ),
                    "default": "at_least",
                },
                "critical": {
                    "type": "boolean",
                    "description": (
                        "Enable critical hit/fumble detection. "
                        "When true, natural 20 = Critical Hit, natural 1 = Critical Fumble "
                        "on d20 rolls. Default: false."
                    ),
                    "default": False,
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
                "count_ones": {
                    "type": "boolean",
                    "description": (
                        "Enable botch/glitch detection by counting 1s. "
                        "WoD Botch: 0 successes and any 1s = Botch. "
                        "Shadowrun Glitch: half or more dice are 1s = Glitch. "
                        "Default: false."
                    ),
                    "default": False,
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

def _error_result(message: str) -> types.CallToolResult:
    """Return an MCP-compliant error CallToolResult with isError=True."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"Error: {message}")],
        isError=True,
    )


def _ok_result(text: str) -> types.CallToolResult:
    """Return a successful CallToolResult."""
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        isError=False,
    )


def _roll_group(group: DiceGroup) -> list[int]:
    """Roll all dice in a group, return list of results."""
    return [random.randint(1, group.sides) for _ in range(group.count)]


def _apply_keep(rolls: list[int], group: DiceGroup) -> tuple[list[int], list[int]]:
    """Apply keep highest/lowest. Returns (kept, dropped)."""
    if group.keep_highest is not None:
        sorted_rolls = sorted(enumerate(rolls), key=lambda x: x[1], reverse=True)
        kept_indices = {idx for idx, _ in sorted_rolls[:group.keep_highest]}
        kept = [r for i, r in enumerate(rolls) if i in kept_indices]
        dropped = [r for i, r in enumerate(rolls) if i not in kept_indices]
        return kept, dropped
    elif group.keep_lowest is not None:
        sorted_rolls = sorted(enumerate(rolls), key=lambda x: x[1])
        kept_indices = {idx for idx, _ in sorted_rolls[:group.keep_lowest]}
        kept = [r for i, r in enumerate(rolls) if i in kept_indices]
        dropped = [r for i, r in enumerate(rolls) if i not in kept_indices]
        return kept, dropped
    return rolls, []


# ---------------------------------------------------------------------------
# roll_dice implementation
# ---------------------------------------------------------------------------

def _execute_roll_dice(
    notation: str,
    advantage: str = "normal",
    target: int | None = None,
    target_mode: str = "at_least",
    critical: bool = False,
) -> types.CallToolResult:
    """Execute a dice roll and return a CallToolResult."""
    try:
        parsed = parse(notation)
    except ValueError as e:
        return _error_result(str(e))

    # Advantage/disadvantage: only valid for single d20 group without keep
    adv_applicable = (
        advantage != "normal"
        and len(parsed.groups) == 1
        and parsed.groups[0].sides == 20
        and parsed.groups[0].count == 1
        and not parsed.groups[0].negative
        and parsed.groups[0].keep_highest is None
        and parsed.groups[0].keep_lowest is None
    )

    if advantage != "normal" and not adv_applicable:
        return _error_result(
            "어드밴티지/디스어드밴티지는 단일 1d20 굴림에만 적용 가능합니다. "
            f"현재 표현식: '{notation}'"
        )

    lines: list[str] = []
    natural_value: int | None = None  # for critical detection on d20

    if adv_applicable:
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        if advantage == "advantage":
            chosen = max(roll1, roll2)
            label = "Advantage"
        else:
            chosen = min(roll1, roll2)
            label = "Disadvantage"

        natural_value = chosen
        total = chosen + parsed.modifier
        lines.append(f"Roll ({label}): 1d20 → [{roll1}, {roll2}] → 선택: {chosen}")
        if parsed.modifier != 0:
            sign = "+" if parsed.modifier > 0 else ""
            lines.append(f"Modifier: {sign}{parsed.modifier}")
        lines.append(f"Total: {total}")
    else:
        all_results: list[tuple[DiceGroup, list[int], list[int], list[int]]] = []
        for group in parsed.groups:
            rolls = _roll_group(group)
            kept, dropped = _apply_keep(rolls, group)
            all_results.append((group, rolls, kept, dropped))

        positive_sum = 0
        negative_sum = 0

        for group, rolls, kept, dropped in all_results:
            prefix = "-" if group.negative else ""
            has_keep = group.keep_highest is not None or group.keep_lowest is not None

            if has_keep:
                # Show all rolls with dropped ones struck through
                rolls_display = []
                kept_set = list(kept)
                dropped_set = list(dropped)
                for r in rolls:
                    if r in dropped_set:
                        rolls_display.append(f"~~{r}~~")
                        dropped_set.remove(r)
                    else:
                        rolls_display.append(str(r))
                        if r in kept_set:
                            kept_set.remove(r)

                keep_label = ""
                if group.keep_highest:
                    keep_label = f"kh{group.keep_highest}"
                elif group.keep_lowest:
                    keep_label = f"kl{group.keep_lowest}"

                rolls_str = ", ".join(rolls_display)
                lines.append(
                    f"{prefix}{group.count}d{group.sides}{keep_label}: "
                    f"[{rolls_str}] → kept: [{', '.join(str(k) for k in kept)}]"
                )
            else:
                rolls_str = ", ".join(str(r) for r in rolls)
                lines.append(f"{prefix}{group.count}d{group.sides}: [{rolls_str}]")

            if group.negative:
                negative_sum += sum(kept)
            else:
                positive_sum += sum(kept)

            # Track natural value for critical detection (single d20 group)
            if (
                not group.negative
                and group.sides == 20
                and len(parsed.groups) == 1
            ):
                if has_keep and len(kept) == 1:
                    natural_value = kept[0]
                elif not has_keep and group.count == 1:
                    natural_value = rolls[0]

        dice_total = positive_sum - negative_sum
        total = dice_total + parsed.modifier

        # Build the Total line
        if negative_sum > 0:
            total_parts = [f"{positive_sum} - {negative_sum}"]
            if parsed.modifier != 0:
                sign = "+" if parsed.modifier > 0 else ""
                total_parts.append(f"{sign}{parsed.modifier}")
            lines.append(f"Total: {' '.join(total_parts)} = {total}")
        else:
            if parsed.modifier != 0:
                sign = "+" if parsed.modifier > 0 else ""
                lines.append(f"Modifier: {sign}{parsed.modifier}")
            lines.append(f"Total: {total}")

    # Critical detection (feature toggle)
    if critical and natural_value is not None:
        if natural_value == 20:
            lines.append("💥 CRITICAL HIT! (Natural 20)")
        elif natural_value == 1:
            lines.append("💀 CRITICAL FUMBLE! (Natural 1)")

    # Target check with mode
    if target is not None:
        if target_mode == "at_most":
            # CoC/BRP style: success if result <= target
            if total <= target:
                lines.append(f"판정: 성공! ({total} ≤ {target})")
            else:
                lines.append(f"판정: 실패 ({total} > {target})")
        else:
            # D&D style: success if result >= target
            if total >= target:
                lines.append(f"판정: 성공! ({total} ≥ {target})")
            else:
                lines.append(f"판정: 실패 ({total} < {target})")

    result_text = "\n".join(lines)
    history.add(
        "roll_dice",
        notation + (f" ({advantage})" if advantage != "normal" else ""),
        result_text,
    )
    return _ok_result(result_text)


# ---------------------------------------------------------------------------
# roll_pool implementation
# ---------------------------------------------------------------------------

def _execute_roll_pool(
    pool: int,
    sides: int = 10,
    target: int = 8,
    explode: bool = False,
    double_on: int | None = None,
    count_ones: bool = False,
) -> types.CallToolResult:
    """Execute a dice pool roll and return a CallToolResult."""
    if pool < 1 or pool > 50:
        return _error_result("다이스 풀 크기는 1~50 사이여야 합니다.")
    if sides < 2:
        return _error_result("주사위 면 수는 2 이상이어야 합니다.")
    if target < 1 or target > sides:
        return _error_result(f"성공 기준값은 1~{sides} 사이여야 합니다.")
    if double_on is not None and double_on < target:
        return _error_result(f"double_on({double_on})은 target({target}) 이상이어야 합니다.")

    rolls_display: list[str] = []
    successes = 0
    ones_count = 0
    total_dice_rolled = 0

    for _ in range(pool):
        roll = random.randint(1, sides)
        chain = [roll]

        while explode and chain[-1] == sides:
            chain.append(random.randint(1, sides))

        die_successes = 0
        for val in chain:
            if val >= target:
                if double_on is not None and val >= double_on:
                    die_successes += 2
                else:
                    die_successes += 1
            if val == 1:
                ones_count += 1

        total_dice_rolled += len(chain)
        successes += die_successes

        if len(chain) > 1:
            chain_str = "→".join(str(v) for v in chain)
            rolls_display.append(f"({chain_str})")
        else:
            rolls_display.append(str(roll))

    lines: list[str] = []
    header = f"Dice Pool: {pool}d{sides} (target ≥ {target}"
    if explode:
        header += ", exploding"
    if double_on is not None:
        header += f", double on ≥ {double_on}"
    if count_ones:
        header += ", botch/glitch detection ON"
    header += ")"
    lines.append(header)
    lines.append(f"Rolls: [{', '.join(rolls_display)}]")
    lines.append(f"Successes: {successes}")

    # Botch/Glitch detection (feature toggle)
    if count_ones:
        lines.append(f"1s rolled: {ones_count}")

        # WoD Botch: 0 successes and at least one 1
        if successes == 0 and ones_count > 0:
            lines.append("🔥 BOTCH! (0 successes with 1s — WoD rule)")

        # Shadowrun Glitch: half or more of total dice are 1s
        if ones_count >= (total_dice_rolled + 1) // 2:
            if successes == 0:
                lines.append("💀 CRITICAL GLITCH! (half+ dice are 1s, 0 successes — Shadowrun rule)")
            else:
                lines.append("⚠️ GLITCH! (half+ dice are 1s — Shadowrun rule)")

    result_text = "\n".join(lines)
    desc = f"{pool}d{sides} pool (target≥{target})"
    history.add("roll_pool", desc, result_text)
    return _ok_result(result_text)


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> types.CallToolResult:
    args = arguments or {}

    if name == "roll_dice":
        notation = args.get("notation")
        if not notation:
            return _error_result("'notation' 파라미터가 필요합니다. 예: '1d20+5', '4d6kh3'")
        advantage = args.get("advantage", "normal")
        if advantage not in ("normal", "advantage", "disadvantage"):
            return _error_result(
                "'advantage'는 'normal', 'advantage', 'disadvantage' 중 하나여야 합니다."
            )
        target = args.get("target")
        target_mode = args.get("target_mode", "at_least")
        if target_mode not in ("at_least", "at_most"):
            return _error_result(
                "'target_mode'는 'at_least' 또는 'at_most'여야 합니다."
            )
        critical = bool(args.get("critical", False))
        return _execute_roll_dice(notation, advantage, target, target_mode, critical)

    elif name == "roll_pool":
        pool = args.get("pool")
        if pool is None:
            return _error_result("'pool' 파라미터가 필요합니다.")
        return _execute_roll_pool(
            pool=int(pool),
            sides=int(args.get("sides", 10)),
            target=int(args.get("target", 8)),
            explode=bool(args.get("explode", False)),
            double_on=int(args["double_on"]) if args.get("double_on") is not None else None,
            count_ones=bool(args.get("count_ones", False)),
        )

    elif name == "get_history":
        limit = int(args.get("limit", 10))
        records = history.get(limit)
        if not records:
            return _ok_result("굴림 기록이 없습니다.")

        lines = [f"=== 최근 {len(records)}개 굴림 기록 ==="]
        for i, rec in enumerate(records, 1):
            lines.append(f"[{i}] ({rec.timestamp}) {rec.tool}: {rec.input_desc}")
            lines.append(f"    → {rec.result_text.split(chr(10))[-1]}")
        return _ok_result("\n".join(lines))

    elif name == "clear_history":
        count = history.clear()
        return _ok_result(f"굴림 기록 {count}건을 삭제했습니다.")

    else:
        return _error_result(f"알 수 없는 tool입니다: '{name}'")


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
                server_version="3.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main():
    """Entry point for the CLI command"""
    asyncio.run(_run())
