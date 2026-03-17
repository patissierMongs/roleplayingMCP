"""
Strategy Pattern implementations for TRPG dice mechanics.

Each strategy encapsulates a family of interchangeable algorithms:
  - DegreeStrategy: success-degree calculations (CoC, PF2e, PbtA)
  - RollStrategy: dice-roll execution paths (standard, advantage, bonus/penalty)
  - PoolStrategy: dice-pool counting (WoD, Shadowrun)
"""

from .base import DegreeStrategy, RollStrategy, PoolStrategy
from .degrees import CoCDegreeStrategy, PF2eDegreeStrategy, PbtADegreeStrategy, DEGREE_REGISTRY
from .rolls import StandardRollStrategy, AdvantageRollStrategy, BonusPenaltyRollStrategy
from .pools import StandardPoolStrategy

__all__ = [
    "DegreeStrategy",
    "RollStrategy",
    "PoolStrategy",
    "CoCDegreeStrategy",
    "PF2eDegreeStrategy",
    "PbtADegreeStrategy",
    "DEGREE_REGISTRY",
    "StandardRollStrategy",
    "AdvantageRollStrategy",
    "BonusPenaltyRollStrategy",
    "StandardPoolStrategy",
]
