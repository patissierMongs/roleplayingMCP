"""
Roll execution Strategy implementations.

Three mutually exclusive paths:
  - StandardRollStrategy: normal dice (compound, fudge, keep)
  - AdvantageRollStrategy: D&D 5e advantage/disadvantage (1d20 only)
  - BonusPenaltyRollStrategy: CoC bonus/penalty dice (1d100 only)
"""

import random

from .base import RollStrategy
from ..dice_parser import DiceGroup, ParsedNotation
from ..models import RollResult


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


class StandardRollStrategy(RollStrategy):
    """Standard dice roll: compound groups, fudge, keep highest/lowest."""

    def execute(self, parsed: ParsedNotation, **kwargs) -> RollResult:
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

        result = RollResult.ok(lines)
        result.total = total  # type: ignore[attr-defined]
        result.natural_value = natural_value  # type: ignore[attr-defined]
        return result


class AdvantageRollStrategy(RollStrategy):
    """D&D 5e advantage/disadvantage: roll 1d20 twice, pick higher/lower."""

    def execute(self, parsed: ParsedNotation, **kwargs) -> RollResult:
        advantage: bool = kwargs.get("advantage", False)

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

        lines: list[str] = []
        lines.append(f"Roll ({label}): 1d20 → [{roll1}, {roll2}] → picked: {chosen}")
        if parsed.modifier != 0:
            sign = "+" if parsed.modifier > 0 else ""
            lines.append(f"Modifier: {sign}{parsed.modifier}")
        lines.append(f"Total: {total}")

        result = RollResult.ok(lines)
        result.total = total  # type: ignore[attr-defined]
        result.natural_value = natural_value  # type: ignore[attr-defined]
        return result


class BonusPenaltyRollStrategy(RollStrategy):
    """CoC 7e bonus/penalty dice: roll d100 with extra tens digits."""

    def execute(self, parsed: ParsedNotation, **kwargs) -> RollResult:
        bonus_dice: int = kwargs.get("bonus_dice", 0)
        penalty_dice: int = kwargs.get("penalty_dice", 0)

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

        result = RollResult.ok(lines)
        result.total = total  # type: ignore[attr-defined]
        result.natural_value = None  # type: ignore[attr-defined]
        return result
