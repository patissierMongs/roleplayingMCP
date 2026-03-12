"""
Dice notation parser for standard TRPG dice expressions.

Supports:
  - NdM       : Roll N dice with M sides (e.g. 2d6, 1d20, 1d100)
  - NdF       : Roll N fudge/FATE dice (each: -1, 0, +1)
  - NdM+K     : With positive modifier (e.g. 1d20+5)
  - NdM-K     : With negative modifier (e.g. 2d6-1)
  - Compound  : Multiple groups (e.g. 2d6+1d4+3)
  - Negative dice: NdM with subtraction (e.g. 3d20-2d20)
  - Keep highest: NdMkhX (e.g. 4d6kh3 = roll 4d6, keep highest 3)
  - Keep lowest:  NdMklX (e.g. 2d20kl1 = roll 2d20, keep lowest 1)
"""

import re
from dataclasses import dataclass

# Pattern: optional sign, then NdM/NdF with optional kh/kl, or plain number
_TOKEN_RE = re.compile(
    r'([+-]?)\s*(?:(\d+)d([fF]|\d+)(?:kh(\d+)|kl(\d+))?|(\d+))'
)


@dataclass
class DiceGroup:
    """A single dice group like +2d6 or -1d4."""
    count: int      # number of dice (always positive)
    sides: int      # faces per die (0 for fudge)
    negative: bool  # True if this group is subtracted
    fudge: bool = False  # True for fudge/FATE dice
    keep_highest: int | None = None  # keep top N dice
    keep_lowest: int | None = None   # keep bottom N dice


@dataclass
class ParsedNotation:
    """Result of parsing a dice notation string."""
    groups: list[DiceGroup]
    modifier: int   # flat +/- constant
    original: str   # the raw notation string


def parse(notation: str) -> ParsedNotation:
    """Parse a dice notation string into structured components."""
    cleaned = notation.replace(" ", "").lower()
    if not cleaned:
        raise ValueError("Empty dice expression.")

    tokens = _TOKEN_RE.findall(cleaned)
    if not tokens:
        raise ValueError(
            f"Invalid dice notation: '{notation}'. Use format like 2d6+3, 1d20+5, 4dF"
        )

    # Verify the entire string is consumed by tokens
    reconstructed = ""
    for sign, num_dice, sides_str, kh, kl, constant in tokens:
        if num_dice and sides_str:
            is_fudge = sides_str.lower() == "f"
            reconstructed += f"{sign}{num_dice}d{'f' if is_fudge else sides_str}"
            if kh:
                reconstructed += f"kh{kh}"
            elif kl:
                reconstructed += f"kl{kl}"
        elif constant:
            reconstructed += f"{sign}{constant}"

    def _normalize(s: str) -> str:
        return s.lstrip("+")

    if _normalize(reconstructed) != _normalize(cleaned):
        raise ValueError(
            f"Invalid dice notation: '{notation}'. Use format like 2d6+3, 1d20+5, 4dF"
        )

    groups: list[DiceGroup] = []
    modifier = 0

    for sign, num_dice, sides_str, kh, kl, constant in tokens:
        is_negative = sign == "-"

        if num_dice and sides_str:
            n = int(num_dice)
            is_fudge = sides_str.lower() == "f"
            s = 0 if is_fudge else int(sides_str)

            if n < 1:
                raise ValueError(f"Dice count must be at least 1: {n}")
            if not is_fudge and s < 1:
                raise ValueError(f"Dice sides must be at least 1: {n}d{s}")
            if n > 100:
                raise ValueError(f"Too many dice (max 100): {n}")
            if not is_fudge and s > 1000:
                raise ValueError(f"Too many sides (max 1000): {n}d{s}")

            keep_highest = int(kh) if kh else None
            keep_lowest = int(kl) if kl else None

            if keep_highest is not None and keep_highest > n:
                raise ValueError(
                    f"keep highest ({keep_highest}) exceeds dice count ({n})."
                )
            if keep_highest is not None and keep_highest < 1:
                raise ValueError("keep highest must be at least 1.")
            if keep_lowest is not None and keep_lowest > n:
                raise ValueError(
                    f"keep lowest ({keep_lowest}) exceeds dice count ({n})."
                )
            if keep_lowest is not None and keep_lowest < 1:
                raise ValueError("keep lowest must be at least 1.")

            groups.append(DiceGroup(
                count=n, sides=s, negative=is_negative,
                fudge=is_fudge,
                keep_highest=keep_highest, keep_lowest=keep_lowest,
            ))
        elif constant:
            val = int(constant)
            modifier += -val if is_negative else val

    if not groups:
        raise ValueError(
            f"No dice found in '{notation}'. Constants alone are not valid."
        )

    return ParsedNotation(groups=groups, modifier=modifier, original=notation)
