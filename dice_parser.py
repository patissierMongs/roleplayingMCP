"""
Dice notation parser for standard TRPG dice expressions.

Supports:
  - NdM       : Roll N dice with M sides (e.g. 2d6, 1d20, 1d100)
  - NdM+K     : With positive modifier (e.g. 1d20+5)
  - NdM-K     : With negative modifier (e.g. 2d6-1)
  - Compound  : Multiple groups (e.g. 2d6+1d4+3)
  - Negative dice: NdM with subtraction (e.g. 3d20-2d20 means roll 3, subtract 2)
"""

import re
from dataclasses import dataclass

# Pattern: optional sign, then either NdM or plain number
_TOKEN_RE = re.compile(r'([+-]?)\s*(?:(\d+)d(\d+)|(\d+))')


@dataclass
class DiceGroup:
    """A single dice group like +2d6 or -1d4."""
    count: int      # number of dice (always positive)
    sides: int      # faces per die
    negative: bool  # True if this group is subtracted


@dataclass
class ParsedNotation:
    """Result of parsing a dice notation string."""
    groups: list[DiceGroup]
    modifier: int   # flat +/- constant
    original: str   # the raw notation string


def parse(notation: str) -> ParsedNotation:
    """Parse a dice notation string into structured components.

    Args:
        notation: A dice notation string like "2d6+3" or "1d20+5"

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
            f"올바른 다이스 노테이션이 아닙니다: '{notation}'. 예: 2d6+3, 1d20+5"
        )

    # Verify the entire string is consumed by tokens
    reconstructed = ""
    for sign, num_dice, sides, constant in tokens:
        if num_dice and sides:
            reconstructed += f"{sign}{num_dice}d{sides}"
        elif constant:
            reconstructed += f"{sign}{constant}"

    # Normalize: strip leading '+', handle no-sign on first token
    def _normalize(s: str) -> str:
        s = s.lstrip("+")
        return s

    if _normalize(reconstructed) != _normalize(cleaned):
        raise ValueError(
            f"올바른 다이스 노테이션이 아닙니다: '{notation}'. 예: 2d6+3, 1d20+5"
        )

    groups: list[DiceGroup] = []
    modifier = 0

    for sign, num_dice, sides, constant in tokens:
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
            groups.append(DiceGroup(count=n, sides=s, negative=is_negative))
        elif constant:
            val = int(constant)
            modifier += -val if is_negative else val

    if not groups:
        raise ValueError(
            f"주사위가 포함되지 않았습니다: '{notation}'. 상수만으로는 굴릴 수 없습니다."
        )

    return ParsedNotation(groups=groups, modifier=modifier, original=notation)
