"""
DiceRoller — Facade for all dice operations.

Responsibilities:
  1. Validate parameters
  2. Execute rolls (private methods, NOT fake strategies)
  3. Delegate degree calculation to DegreeStrategy (genuine Strategy)
  4. Record results in history

Factor VI (Processes): No global state — all dependencies injected.
"""

import random
from typing import Any, Protocol

from .config import ServerConfig
from .dice_parser import parse, DiceGroup, ParsedNotation
from .models import RollRecord, RollResult
from .strategies.base import DegreeStrategy
from .strategies.degrees import DEGREE_REGISTRY


class HistoryBackend(Protocol):
    """Protocol for history storage — 12-Factor backing service."""

    def add(self, tool: str, input_desc: str, result_text: str) -> None: ...
    def get(self, limit: int = 10) -> list[RollRecord]: ...
    def clear(self) -> int: ...


class DiceRoller:
    """Facade coordinating validation, rolls, degrees, and history."""

    def __init__(
        self,
        config: ServerConfig,
        history: HistoryBackend,
        degree_registry: dict[str, DegreeStrategy] | None = None,
    ):
        self._config = config
        self._history = history
        self._degrees = degree_registry or DEGREE_REGISTRY
        self._last_roll: dict[str, Any] | None = None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def roll_dice(
        self,
        notation: str,
        advantage: bool = False,
        disadvantage: bool = False,
        bonus_dice: int = 0,
        penalty_dice: int = 0,
        target: int | None = None,
        target_mode: str = "at_least",
        critical: bool = False,
        degrees: str | None = None,
    ) -> RollResult:
        # --- Validation ---
        if advantage and disadvantage:
            return RollResult.error("Cannot use both advantage and disadvantage.")
        if bonus_dice > 0 and penalty_dice > 0:
            return RollResult.error("Cannot use both bonus_dice and penalty_dice.")

        has_adv = advantage or disadvantage
        has_bp = bonus_dice > 0 or penalty_dice > 0
        if has_adv and has_bp:
            return RollResult.error(
                "Cannot combine advantage/disadvantage with bonus/penalty dice."
            )
        if degrees is not None and degrees not in self._degrees:
            valid = ", ".join(f"'{k}'" for k in self._degrees)
            return RollResult.error(f"degrees must be one of: {valid}.")

        degree_strategy = self._degrees.get(degrees) if degrees else None
        if degree_strategy and degree_strategy.requires_target and target is None:
            return RollResult.error(f"degrees='{degrees}' requires target to be set.")

        try:
            parsed = parse(notation)
        except ValueError as e:
            return RollResult.error(str(e))

        # --- Applicability checks ---
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
            return RollResult.error(
                f"Advantage/disadvantage only applies to a single 1d20 roll. "
                f"Got: '{notation}'"
            )

        bp_applicable = (
            has_bp
            and len(parsed.groups) == 1
            and parsed.groups[0].sides == 100
            and parsed.groups[0].count == 1
            and not parsed.groups[0].negative
            and not parsed.groups[0].fudge
        )
        if has_bp and not bp_applicable:
            return RollResult.error(
                f"Bonus/penalty dice only applies to a single 1d100 roll. "
                f"Got: '{notation}'"
            )

        # --- Execute the appropriate roll path ---
        if adv_applicable:
            result = self._roll_advantage(parsed, advantage=advantage)
        elif bp_applicable:
            result = self._roll_bonus_penalty(parsed, bonus_dice, penalty_dice)
        else:
            result = self._roll_standard(parsed)

        # --- Degree post-processing (genuine Strategy dispatch) ---
        if degree_strategy:
            result.lines.extend(
                degree_strategy.calculate(
                    result.total, target, result.natural_value, critical
                )
            )
        else:
            if critical and result.natural_value is not None:
                if result.natural_value == 20:
                    result.lines.append("💥 CRITICAL HIT! (Natural 20)")
                elif result.natural_value == 1:
                    result.lines.append("💀 CRITICAL FUMBLE! (Natural 1)")

            if target is not None:
                if target_mode == "at_most":
                    if result.total <= target:
                        result.lines.append(f"Check: Success! ({result.total} ≤ {target})")
                    else:
                        result.lines.append(f"Check: Failure ({result.total} > {target})")
                else:
                    if result.total >= target:
                        result.lines.append(f"Check: Success! ({result.total} ≥ {target})")
                    else:
                        result.lines.append(f"Check: Failure ({result.total} < {target})")

        # --- Record ---
        adv_label = (
            " (advantage)" if advantage
            else " (disadvantage)" if disadvantage
            else ""
        )
        self._history.add("roll_dice", notation + adv_label, result.text)
        self._last_roll = {
            "tool": "roll_dice",
            "args": {
                "notation": notation,
                "advantage": advantage,
                "disadvantage": disadvantage,
                "bonus_dice": bonus_dice,
                "penalty_dice": penalty_dice,
                "target": target,
                "target_mode": target_mode,
                "critical": critical,
                "degrees": degrees,
            },
        }
        return result

    def roll_pool(
        self,
        pool: int,
        sides: int = 10,
        target: int = 8,
        explode: bool = False,
        double_on: int | None = None,
        count_ones: bool = False,
    ) -> RollResult:
        max_pool = self._config.max_pool_size
        if pool < 1 or pool > max_pool:
            return RollResult.error(f"Pool size must be between 1 and {max_pool}.")
        if sides < 2:
            return RollResult.error("Sides must be at least 2.")
        if target < 1 or target > sides:
            return RollResult.error(f"Target must be between 1 and {sides}.")
        if double_on is not None and double_on < target:
            return RollResult.error(f"double_on ({double_on}) must be >= target ({target}).")

        result = self._execute_pool(pool, sides, target, explode, double_on, count_ones)

        desc = f"{pool}d{sides} pool (target≥{target})"
        self._history.add("roll_pool", desc, result.text)
        self._last_roll = {
            "tool": "roll_pool",
            "args": {
                "pool": pool,
                "sides": sides,
                "target": target,
                "explode": explode,
                "double_on": double_on,
                "count_ones": count_ones,
            },
        }
        return result

    def reroll(self) -> RollResult:
        if self._last_roll is None:
            return RollResult.error("No previous roll. Use roll_dice or roll_pool first.")

        tool = self._last_roll["tool"]
        args = self._last_roll["args"]
        if tool == "roll_dice":
            result = self.roll_dice(**args)
        elif tool == "roll_pool":
            result = self.roll_pool(**args)
        else:
            return RollResult.error(f"Unknown tool: '{tool}'")

        # Mark reroll in history — overwrite the input_desc that was just written
        # by roll_dice/roll_pool, instead of mutating a returned record.
        if not result.is_error:
            records = self._history.get(1)
            if records:
                records[0].input_desc += " (reroll)"

        return result

    def get_history(self, limit: int = 10) -> RollResult:
        records = self._history.get(limit)
        if not records:
            return RollResult.ok(["No roll history."])
        lines = [f"=== Last {len(records)} roll(s) ==="]
        for i, rec in enumerate(records, 1):
            lines.append(f"[{i}] ({rec.timestamp}) {rec.tool}: {rec.input_desc}")
            lines.append(f"    → {rec.result_text.split(chr(10))[-1]}")
        return RollResult.ok(lines)

    def clear_history(self) -> RollResult:
        count = self._history.clear()
        return RollResult.ok([f"Cleared {count} roll(s) from history."])

    # -----------------------------------------------------------------------
    # Private roll methods — NOT strategies, just implementation details
    # -----------------------------------------------------------------------

    def _roll_standard(self, parsed: ParsedNotation) -> RollResult:
        """Standard dice roll: compound groups, fudge, keep highest/lowest."""
        lines: list[str] = []
        natural_value: int | None = None
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

        return RollResult.ok(lines, total=total, natural_value=natural_value)

    def _roll_advantage(self, parsed: ParsedNotation, advantage: bool) -> RollResult:
        """D&D 5e advantage/disadvantage: roll 1d20 twice, pick higher/lower."""
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        if advantage:
            chosen = max(roll1, roll2)
            label = "Advantage"
        else:
            chosen = min(roll1, roll2)
            label = "Disadvantage"

        total = chosen + parsed.modifier
        lines: list[str] = []
        lines.append(f"Roll ({label}): 1d20 → [{roll1}, {roll2}] → picked: {chosen}")
        if parsed.modifier != 0:
            sign = "+" if parsed.modifier > 0 else ""
            lines.append(f"Modifier: {sign}{parsed.modifier}")
        lines.append(f"Total: {total}")

        return RollResult.ok(lines, total=total, natural_value=chosen)

    def _roll_bonus_penalty(
        self, parsed: ParsedNotation, bonus_dice: int, penalty_dice: int,
    ) -> RollResult:
        """CoC 7e bonus/penalty dice: roll d100 with extra tens digits."""
        units = random.randint(0, 9)
        num_tens = 1 + bonus_dice + penalty_dice
        tens_rolls = [random.randint(0, 9) for _ in range(num_tens)]

        possibles = []
        for t in tens_rolls:
            val = t * 10 + units
            possibles.append(100 if val == 0 else val)

        if bonus_dice > 0:
            bp_total = min(possibles)
        elif penalty_dice > 0:
            bp_total = max(possibles)
        else:
            bp_total = possibles[0]

        total = bp_total + parsed.modifier

        lines: list[str] = []
        bp_label = f"Bonus ×{bonus_dice}" if bonus_dice > 0 else f"Penalty ×{penalty_dice}"
        possibles_str = ", ".join(str(p) for p in possibles)
        lines.append(f"1d100 ({bp_label}): [{possibles_str}] → {bp_total}")
        if parsed.modifier != 0:
            sign = "+" if parsed.modifier > 0 else ""
            lines.append(f"Modifier: {sign}{parsed.modifier}")
            lines.append(f"Total: {total}")

        return RollResult.ok(lines, total=total, natural_value=None)

    def _execute_pool(
        self,
        pool: int,
        sides: int,
        target: int,
        explode: bool,
        double_on: int | None,
        count_ones: bool,
    ) -> RollResult:
        """Dice pool: count successes, optional exploding and botch/glitch."""
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

        return RollResult.ok(lines)


# -----------------------------------------------------------------------
# Module-level helpers (pure functions, no state)
# -----------------------------------------------------------------------

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
