"""
Dice pool Strategy implementation.

Supports WoD (exploding, botch), Shadowrun (glitch/critical glitch),
and generic pool-based systems.
"""

import random

from .base import PoolStrategy
from ..models import RollResult


class StandardPoolStrategy(PoolStrategy):
    """Standard dice pool: count successes, optional exploding and botch/glitch."""

    def execute(
        self,
        pool: int,
        sides: int,
        target: int,
        explode: bool,
        double_on: int | None,
        count_ones: bool,
    ) -> RollResult:
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
