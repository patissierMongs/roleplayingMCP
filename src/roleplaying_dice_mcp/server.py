#!/usr/bin/env python3
"""
MCP Dice Server — TRPG-ready dice rolling server using Model Context Protocol.

Tools:
  - roll_dice    : Standard dice notation with adv/dis, bonus/penalty,
                    keep highest/lowest, critical, target modes, degrees
  - roll_pool    : Dice pool with success counting, exploding, botch/glitch
  - reroll       : Re-roll the last roll with same parameters
  - get_history  : Retrieve recent roll history
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
_last_roll: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    types.Tool(
        name="roll_dice",
        description=(
            "Roll dice using standard TRPG notation (e.g. '2d6+3', '1d20+5', '4d6kh3', '4dF'). "
            "Supports advantage/disadvantage, bonus/penalty dice (CoC), "
            "keep highest/lowest, critical detection, flexible target comparison, "
            "and success degree calculation. Returns individual rolls and the total."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "notation": {
                    "type": "string",
                    "description": (
                        "Dice notation string. Examples: '1d20+5', '2d6+3', "
                        "'4d6kh3' (keep highest 3), '2d20kl1' (keep lowest 1), "
                        "'4dF+2' (fudge/FATE dice), '1d100' (percentile)."
                    ),
                },
                "advantage": {
                    "type": "boolean",
                    "description": (
                        "Enable advantage: roll d20 twice, take higher. "
                        "Only applies to single d20 group. Default: false."
                    ),
                    "default": False,
                },
                "disadvantage": {
                    "type": "boolean",
                    "description": (
                        "Enable disadvantage: roll d20 twice, take lower. "
                        "Only applies to single d20 group. Default: false."
                    ),
                    "default": False,
                },
                "bonus_dice": {
                    "type": "integer",
                    "description": (
                        "CoC bonus dice count. Roll extra tens dice on d100, "
                        "keep the lowest (better result). Only for 1d100. Default: 0."
                    ),
                    "default": 0,
                    "minimum": 0,
                    "maximum": 2,
                },
                "penalty_dice": {
                    "type": "integer",
                    "description": (
                        "CoC penalty dice count. Roll extra tens dice on d100, "
                        "keep the highest (worse result). Only for 1d100. Default: 0."
                    ),
                    "default": 0,
                    "minimum": 0,
                    "maximum": 2,
                },
                "target": {
                    "type": "integer",
                    "description": (
                        "Target number (DC/AC/skill value) for success check."
                    ),
                },
                "target_mode": {
                    "type": "string",
                    "enum": ["at_least", "at_most"],
                    "description": (
                        "How to compare result against target. "
                        "'at_least' (default): success if result >= target (D&D). "
                        "'at_most': success if result <= target (CoC/BRP)."
                    ),
                    "default": "at_least",
                },
                "critical": {
                    "type": "boolean",
                    "description": (
                        "Enable critical hit/fumble detection on d20 rolls. "
                        "When used with degrees='pf2e', nat 20/1 shifts degree. "
                        "Default: false."
                    ),
                    "default": False,
                },
                "degrees": {
                    "type": "string",
                    "enum": ["coc", "pf2e", "pbta"],
                    "description": (
                        "Enable success degree calculation. Replaces simple pass/fail. "
                        "'coc': Regular/Hard/Extreme/Critical/Fumble (d100, needs target). "
                        "'pf2e': Crit Success/Success/Fail/Crit Fail by ±10 margin (needs target). "
                        "'pbta': Strong Hit/Weak Hit/Miss (2d6, fixed thresholds)."
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
            "World of Darkness, Shadowrun, etc."
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
                        "Exploding dice: max value triggers reroll. Default: false."
                    ),
                    "default": False,
                },
                "double_on": {
                    "type": "integer",
                    "description": (
                        "Rolls at or above this value count as 2 successes. "
                        "Must be >= target."
                    ),
                },
                "count_ones": {
                    "type": "boolean",
                    "description": (
                        "Enable botch/glitch detection. "
                        "WoD Botch: 0 successes + any 1s. "
                        "Shadowrun Glitch: half+ dice are 1s. Default: false."
                    ),
                    "default": False,
                },
            },
            "required": ["pool"],
        },
    ),
    types.Tool(
        name="reroll",
        description=(
            "Re-roll the last dice roll with identical parameters. "
            "Useful for Inspiration, Lucky feat, reroll abilities."
        ),
        inputSchema={"type": "object", "properties": {}},
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
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"Error: {message}")],
        isError=True,
    )


def _ok_result(text: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
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
# Bonus/Penalty dice (CoC percentile)
# ---------------------------------------------------------------------------

def _roll_percentile_with_bp(
    bonus_dice: int, penalty_dice: int,
) -> tuple[int, int, list[int]]:
    """Roll d100 with CoC bonus/penalty dice.

    Returns: (total, units_digit, list_of_all_possible_results)
    """
    units = random.randint(0, 9)
    num_tens = 1 + bonus_dice + penalty_dice
    tens_rolls = [random.randint(0, 9) for _ in range(num_tens)]

    possibles = []
    for t in tens_rolls:
        result = t * 10 + units
        possibles.append(100 if result == 0 else result)

    if bonus_dice > 0:
        total = min(possibles)
    elif penalty_dice > 0:
        total = max(possibles)
    else:
        total = possibles[0]

    return total, units, possibles


# ---------------------------------------------------------------------------
# Degrees of success
# ---------------------------------------------------------------------------

def _degrees_coc(total: int, target: int) -> list[str]:
    hard = target // 2
    extreme = target // 5
    lines: list[str] = []

    if total == 1:
        lines.append(f"판정: 대성공! (01 — Critical)")
    elif total <= extreme:
        lines.append(f"판정: 익스트림 성공! ({total} ≤ {extreme})")
    elif total <= hard:
        lines.append(f"판정: 하드 성공! ({total} ≤ {hard})")
    elif total <= target:
        lines.append(f"판정: 레귤러 성공 ({total} ≤ {target})")
    elif (target <= 50 and total >= 96) or total == 100:
        lines.append(f"판정: 펌블! ({total})")
    else:
        lines.append(f"판정: 실패 ({total} > {target})")

    lines.append(f"  [Regular ≤{target} / Hard ≤{hard} / Extreme ≤{extreme}]")
    return lines


def _degrees_pf2e(
    total: int, target: int, natural_value: int | None, critical: bool,
) -> list[str]:
    # Base degree by margin
    if total >= target + 10:
        degree = "crit_success"
    elif total >= target:
        degree = "success"
    elif total > target - 10:
        degree = "failure"
    else:
        degree = "crit_failure"

    # Nat 20/1 shifts degree by one step
    nat_shift = ""
    if critical and natural_value is not None:
        upgrades = {
            "crit_failure": "failure",
            "failure": "success",
            "success": "crit_success",
        }
        downgrades = {
            "crit_success": "success",
            "success": "failure",
            "failure": "crit_failure",
        }
        if natural_value == 20 and degree in upgrades:
            degree = upgrades[degree]
            nat_shift = " (Nat 20 ↑)"
        elif natural_value == 1 and degree in downgrades:
            degree = downgrades[degree]
            nat_shift = " (Nat 1 ↓)"

    labels = {
        "crit_success": "대성공!",
        "success": "성공",
        "failure": "실패",
        "crit_failure": "대실패!",
    }
    margin = total - target
    sign = "+" if margin >= 0 else ""
    lines = [
        f"판정: {labels[degree]}{nat_shift} (차이: {sign}{margin})",
        f"  [DC {target}: 대성공 ≥{target + 10} / 성공 ≥{target} / 대실패 ≤{target - 10}]",
    ]
    return lines


def _degrees_pbta(total: int) -> list[str]:
    if total >= 10:
        line = f"판정: Strong Hit! ({total} ≥ 10)"
    elif total >= 7:
        line = f"판정: Weak Hit ({total}: 7-9)"
    else:
        line = f"판정: Miss ({total} ≤ 6)"
    return [line, "  [Strong ≥10 / Weak 7-9 / Miss ≤6]"]


# ---------------------------------------------------------------------------
# roll_dice implementation
# ---------------------------------------------------------------------------

def _execute_roll_dice(
    notation: str,
    advantage: bool = False,
    disadvantage: bool = False,
    bonus_dice: int = 0,
    penalty_dice: int = 0,
    target: int | None = None,
    target_mode: str = "at_least",
    critical: bool = False,
    degrees: str | None = None,
) -> types.CallToolResult:
    # --- Validation ---
    if advantage and disadvantage:
        return _error_result("advantage와 disadvantage를 동시에 사용할 수 없습니다.")
    if bonus_dice > 0 and penalty_dice > 0:
        return _error_result("bonus_dice와 penalty_dice를 동시에 사용할 수 없습니다.")
    has_adv = advantage or disadvantage
    has_bp = bonus_dice > 0 or penalty_dice > 0
    if has_adv and has_bp:
        return _error_result(
            "advantage/disadvantage와 bonus/penalty dice를 동시에 사용할 수 없습니다."
        )
    if degrees is not None and degrees not in ("coc", "pf2e", "pbta"):
        return _error_result("degrees는 'coc', 'pf2e', 'pbta' 중 하나여야 합니다.")
    if degrees in ("coc", "pf2e") and target is None:
        return _error_result(f"'{degrees}' 성공 단계 판정에는 target이 필요합니다.")

    try:
        parsed = parse(notation)
    except ValueError as e:
        return _error_result(str(e))

    # Check applicability of advantage
    adv_applicable = (
        has_adv
        and len(parsed.groups) == 1
        and parsed.groups[0].sides == 20
        and parsed.groups[0].count == 1
        and not parsed.groups[0].negative
        and not parsed.groups[0].fudge
        and parsed.groups[0].keep_highest is None
        and parsed.groups[0].keep_lowest is None
    )
    if has_adv and not adv_applicable:
        return _error_result(
            "어드밴티지/디스어드밴티지는 단일 1d20 굴림에만 적용 가능합니다. "
            f"현재 표현식: '{notation}'"
        )

    # Check applicability of bonus/penalty
    bp_applicable = (
        has_bp
        and len(parsed.groups) == 1
        and parsed.groups[0].sides == 100
        and parsed.groups[0].count == 1
        and not parsed.groups[0].negative
        and not parsed.groups[0].fudge
    )
    if has_bp and not bp_applicable:
        return _error_result(
            "보너스/페널티 다이스는 단일 1d100 굴림에만 적용 가능합니다. "
            f"현재 표현식: '{notation}'"
        )

    lines: list[str] = []
    natural_value: int | None = None
    total: int = 0

    # --- Path A: Advantage/Disadvantage ---
    if adv_applicable:
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        if advantage:
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

    # --- Path B: Bonus/Penalty dice (CoC percentile) ---
    elif bp_applicable:
        bp_total, units, possibles = _roll_percentile_with_bp(bonus_dice, penalty_dice)
        total = bp_total + parsed.modifier
        bp_label = f"보너스 ×{bonus_dice}" if bonus_dice > 0 else f"페널티 ×{penalty_dice}"
        possibles_str = ", ".join(str(p) for p in possibles)
        lines.append(f"1d100 ({bp_label}): [{possibles_str}] → {bp_total}")
        if parsed.modifier != 0:
            sign = "+" if parsed.modifier > 0 else ""
            lines.append(f"Modifier: {sign}{parsed.modifier}")
            lines.append(f"Total: {total}")

    # --- Path C: Normal roll ---
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

            # --- Fudge dice display ---
            if group.fudge:
                fudge_symbols = {-1: "-", 0: "0", 1: "+"}
                if has_keep:
                    rolls_display = []
                    dropped_set = list(dropped)
                    for r in rolls:
                        sym = fudge_symbols[r]
                        if r in dropped_set:
                            rolls_display.append(f"~~{sym}~~")
                            dropped_set.remove(r)
                        else:
                            rolls_display.append(sym)
                    keep_label = ""
                    if group.keep_highest:
                        keep_label = f"kh{group.keep_highest}"
                    elif group.keep_lowest:
                        keep_label = f"kl{group.keep_lowest}"
                    kept_str = ", ".join(fudge_symbols[k] for k in kept)
                    lines.append(
                        f"{prefix}{group.count}dFate{keep_label}: "
                        f"[{', '.join(rolls_display)}] → kept: [{kept_str}]"
                    )
                else:
                    rolls_str = ", ".join(fudge_symbols[r] for r in rolls)
                    lines.append(f"{prefix}{group.count}dFate: [{rolls_str}]")

            # --- Normal dice display ---
            elif has_keep:
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

            # Track natural value for critical/pf2e (single d20 group)
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

    # --- Degrees mode: replaces simple target check + critical ---
    if degrees:
        if degrees == "coc":
            lines.extend(_degrees_coc(total, target))
        elif degrees == "pf2e":
            lines.extend(_degrees_pf2e(total, target, natural_value, critical))
        elif degrees == "pbta":
            lines.extend(_degrees_pbta(total))
    else:
        # Standard critical detection
        if critical and natural_value is not None:
            if natural_value == 20:
                lines.append("💥 CRITICAL HIT! (Natural 20)")
            elif natural_value == 1:
                lines.append("💀 CRITICAL FUMBLE! (Natural 1)")

        # Standard target check
        if target is not None:
            if target_mode == "at_most":
                if total <= target:
                    lines.append(f"판정: 성공! ({total} ≤ {target})")
                else:
                    lines.append(f"판정: 실패 ({total} > {target})")
            else:
                if total >= target:
                    lines.append(f"판정: 성공! ({total} ≥ {target})")
                else:
                    lines.append(f"판정: 실패 ({total} < {target})")

    result_text = "\n".join(lines)
    adv_label = (
        " (advantage)" if advantage
        else " (disadvantage)" if disadvantage
        else ""
    )
    history.add("roll_dice", notation + adv_label, result_text)
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
    hdr = f"Dice Pool: {pool}d{sides} (target ≥ {target}"
    if explode:
        hdr += ", exploding"
    if double_on is not None:
        hdr += f", double on ≥ {double_on}"
    if count_ones:
        hdr += ", botch/glitch detection ON"
    hdr += ")"
    lines.append(hdr)
    lines.append(f"Rolls: [{', '.join(rolls_display)}]")
    lines.append(f"Successes: {successes}")

    if count_ones:
        lines.append(f"1s rolled: {ones_count}")
        if successes == 0 and ones_count > 0:
            lines.append("🔥 BOTCH! (0 successes with 1s — WoD rule)")
        if ones_count >= (total_dice_rolled + 1) // 2:
            if successes == 0:
                lines.append(
                    "💀 CRITICAL GLITCH! (half+ dice are 1s, 0 successes — Shadowrun rule)"
                )
            else:
                lines.append("⚠️ GLITCH! (half+ dice are 1s — Shadowrun rule)")

    result_text = "\n".join(lines)
    desc = f"{pool}d{sides} pool (target≥{target})"
    history.add("roll_pool", desc, result_text)
    return _ok_result(result_text)


# ---------------------------------------------------------------------------
# Roll dispatcher (supports reroll via stored params)
# ---------------------------------------------------------------------------

def _dispatch_roll(name: str, args: dict[str, Any]) -> types.CallToolResult:
    global _last_roll

    if name == "roll_dice":
        notation = args.get("notation")
        if not notation:
            return _error_result("'notation' 파라미터가 필요합니다. 예: '1d20+5', '4dF'")

        advantage = bool(args.get("advantage", False))
        disadvantage = bool(args.get("disadvantage", False))
        bonus_dice = int(args.get("bonus_dice", 0))
        penalty_dice = int(args.get("penalty_dice", 0))
        target = args.get("target")
        target_mode = args.get("target_mode", "at_least")
        if target_mode not in ("at_least", "at_most"):
            return _error_result("'target_mode'는 'at_least' 또는 'at_most'여야 합니다.")
        critical = bool(args.get("critical", False))
        degrees = args.get("degrees")

        _last_roll = {"tool": name, "args": dict(args)}
        return _execute_roll_dice(
            notation, advantage, disadvantage,
            bonus_dice, penalty_dice,
            target, target_mode, critical, degrees,
        )

    elif name == "roll_pool":
        pool = args.get("pool")
        if pool is None:
            return _error_result("'pool' 파라미터가 필요합니다.")

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
            count_ones=bool(args.get("count_ones", False)),
        )

    return _error_result(f"알 수 없는 tool입니다: '{name}'")


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
            return _error_result("이전 굴림이 없습니다. 먼저 roll_dice 또는 roll_pool을 사용하세요.")
        result = _dispatch_roll(_last_roll["tool"], _last_roll["args"])
        # Mark reroll in history
        if not result.isError:
            records = history.get(1)
            if records:
                records[0].input_desc += " (reroll)"
        return result

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
                server_version="4.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main():
    """Entry point for the CLI command"""
    asyncio.run(_run())
