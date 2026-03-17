"""
DiceRoller — Facade that selects and delegates to the right Strategy.

This is the single entry point for all roll logic. It:
  1. Validates parameters
  2. Selects the appropriate RollStrategy or PoolStrategy
  3. Applies DegreeStrategy post-processing
  4. Records results in history

Factor VI (Processes): No global state — all dependencies injected.
"""

from typing import Any, Protocol

from .config import ServerConfig
from .dice_parser import parse
from .models import RollResult
from .strategies.base import DegreeStrategy
from .strategies.degrees import DEGREE_REGISTRY
from .strategies.rolls import (
    StandardRollStrategy,
    AdvantageRollStrategy,
    BonusPenaltyRollStrategy,
)
from .strategies.pools import StandardPoolStrategy


class HistoryBackend(Protocol):
    """Protocol for history storage — 12-Factor backing service."""

    def add(self, tool: str, input_desc: str, result_text: str) -> None: ...
    def get(self, limit: int = 10) -> list: ...
    def clear(self) -> int: ...


class DiceRoller:
    """Facade coordinating strategies, validation, and history."""

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

        # Strategy instances
        self._standard_roll = StandardRollStrategy()
        self._advantage_roll = AdvantageRollStrategy()
        self._bonus_penalty_roll = BonusPenaltyRollStrategy()
        self._pool = StandardPoolStrategy()

    # --- Public API ---

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

        # --- Select strategy ---
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

        # --- Execute via selected strategy ---
        if adv_applicable:
            result = self._advantage_roll.execute(parsed, advantage=advantage)
        elif bp_applicable:
            result = self._bonus_penalty_roll.execute(
                parsed, bonus_dice=bonus_dice, penalty_dice=penalty_dice
            )
        else:
            result = self._standard_roll.execute(parsed)

        total: int = getattr(result, "total", 0)
        natural_value: int | None = getattr(result, "natural_value", None)

        # --- Degree post-processing ---
        if degree_strategy:
            result.lines.extend(
                degree_strategy.calculate(total, target, natural_value, critical)
            )
        else:
            # Standard critical detection
            if critical and natural_value is not None:
                if natural_value == 20:
                    result.lines.append("💥 CRITICAL HIT! (Natural 20)")
                elif natural_value == 1:
                    result.lines.append("💀 CRITICAL FUMBLE! (Natural 1)")

            # Standard target check
            if target is not None:
                if target_mode == "at_most":
                    if total <= target:
                        result.lines.append(f"Check: Success! ({total} ≤ {target})")
                    else:
                        result.lines.append(f"Check: Failure ({total} > {target})")
                else:
                    if total >= target:
                        result.lines.append(f"Check: Success! ({total} ≥ {target})")
                    else:
                        result.lines.append(f"Check: Failure ({total} < {target})")

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

        result = self._pool.execute(pool, sides, target, explode, double_on, count_ones)

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

        # Mark reroll in history
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
