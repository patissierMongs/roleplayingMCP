"""
Dice notation parser for standard TRPG dice expressions.

Supports:
  - NdM       : Roll N dice with M sides (e.g. 2d6, 1d20, 1d100)
  - NdM+K     : With positive modifier (e.g. 1d20+5)
  - NdM-K     : With negative modifier (e.g. 2d6-1)
  - Compound  : Multiple groups (e.g. 2d6+1d4+3)
  - Negative dice: NdM with subtraction (e.g. 3d20-2d20 means roll 3, subtract 2)
  - Keep highest: NdMkhX (e.g. 4d6kh3 = roll 4d6, keep highest 3)
  - Keep lowest:  NdMklX (e.g. 2d20kl1 = roll 2d20, keep lowest 1)
"""

import re
from dataclasses import dataclass, field

# Pattern: optional sign, then NdM with optional kh/kl, or plain number
_TOKEN_RE = re.compile(
    r'([+-]?)\s*(?:(\d+)d(\d+)(?:kh(\d+)|kl(\d+))?|(\d+))'
)


@dataclass
class DiceGroup:
    """A single dice group like +2d6 or -1d4."""
    count: int      # number of dice (always positive)
    sides: int      # faces per die
    negative: bool  # True if this group is subtracted
    keep_highest: int | None = None  # keep top N dice
    keep_lowest: int | None = None   # keep bottom N dice


@dataclass
class ParsedNotation:
    """Result of parsing a dice notation string."""
    groups: list[DiceGroup]
    modifier: int   # flat +/- constant
    original: str   # the raw notation string


def parse(notation: str) -> ParsedNotation:
    """Parse a dice notation string into structured components.

    Args:
        notation: A dice notation string like "2d6+3" or "4d6kh3"

    Returns:
        ParsedNotation with dice groups and modifier

    Raises:
        ValueError: If the notation is empty or invalid
    """
    cleaned = notation.replace(" ", "").lower()
    if not cleaned:
        raise ValueError("빈 주사위 표현식입니다.")

    tokens = _TOKEN_RE.findall(cleaned)
    if not tokens:
        raise ValueError(
            f"올바른 다이스 노테이션이 아닙니다: '{notation}'. 예: 2d6+3, 1d20+5, 4d6kh3"
        )

    # Verify the entire string is consumed by tokens
    reconstructed = ""
    for sign, num_dice, sides, kh, kl, constant in tokens:
        if num_dice and sides:
            reconstructed += f"{sign}{num_dice}d{sides}"
            if kh:
                reconstructed += f"kh{kh}"
            elif kl:
                reconstructed += f"kl{kl}"
        elif constant:
            reconstructed += f"{sign}{constant}"

    # Normalize: strip leading '+'
    def _normalize(s: str) -> str:
        return s.lstrip("+")

    if _normalize(reconstructed) != _normalize(cleaned):
        raise ValueError(
            f"올바른 다이스 노테이션이 아닙니다: '{notation}'. 예: 2d6+3, 1d20+5, 4d6kh3"
        )

    groups: list[DiceGroup] = []
    modifier = 0

    for sign, num_dice, sides, kh, kl, constant in tokens:
        is_negative = sign == "-"

        if num_dice and sides:
            n = int(num_dice)
            s = int(sides)
            if n < 1:
                raise ValueError(f"주사위 개수는 1 이상이어야 합니다: {n}d{s}")
            if s < 1:
                raise ValueError(f"주사위 면 수는 1 이상이어야 합니다: {n}d{s}")
            if n > 100:
                raise ValueError(f"주사위 개수가 너무 많습니다 (최대 100): {n}d{s}")
            if s > 1000:
                raise ValueError(f"주사위 면 수가 너무 큽니다 (최대 1000): {n}d{s}")

            keep_highest = int(kh) if kh else None
            keep_lowest = int(kl) if kl else None

            if keep_highest is not None and keep_highest > n:
                raise ValueError(
                    f"keep highest({keep_highest})가 주사위 개수({n})보다 클 수 없습니다."
                )
            if keep_highest is not None and keep_highest < 1:
                raise ValueError(f"keep highest는 1 이상이어야 합니다.")
            if keep_lowest is not None and keep_lowest > n:
                raise ValueError(
                    f"keep lowest({keep_lowest})가 주사위 개수({n})보다 클 수 없습니다."
                )
            if keep_lowest is not None and keep_lowest < 1:
                raise ValueError(f"keep lowest는 1 이상이어야 합니다.")

            groups.append(DiceGroup(
                count=n, sides=s, negative=is_negative,
                keep_highest=keep_highest, keep_lowest=keep_lowest,
            ))
        elif constant:
            val = int(constant)
            modifier += -val if is_negative else val

    if not groups:
        raise ValueError(
            f"주사위가 포함되지 않았습니다: '{notation}'. 상수만으로는 굴릴 수 없습니다."
        )

    return ParsedNotation(groups=groups, modifier=modifier, original=notation)
