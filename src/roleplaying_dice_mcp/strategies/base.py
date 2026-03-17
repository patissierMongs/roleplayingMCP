"""
Abstract Strategy interfaces.

Strategy Pattern: Define a family of algorithms, encapsulate each one,
and make them interchangeable.
"""

from abc import ABC, abstractmethod
from ..dice_parser import ParsedNotation
from ..models import RollResult


class DegreeStrategy(ABC):
    """Strategy for calculating success degrees (CoC, PF2e, PbtA)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier (e.g. 'coc', 'pf2e', 'pbta')."""

    @property
    @abstractmethod
    def requires_target(self) -> bool:
        """Whether this degree system needs a target value."""

    @abstractmethod
    def calculate(
        self,
        total: int,
        target: int | None = None,
        natural_value: int | None = None,
        critical: bool = False,
    ) -> list[str]:
        """Return degree-of-success output lines."""


class RollStrategy(ABC):
    """Strategy for executing a dice roll (standard, advantage, bonus/penalty)."""

    @abstractmethod
    def execute(self, parsed: ParsedNotation, **kwargs) -> RollResult:
        """Execute the roll and return a RollResult."""


class PoolStrategy(ABC):
    """Strategy for executing a dice pool roll."""

    @abstractmethod
    def execute(
        self,
        pool: int,
        sides: int,
        target: int,
        explode: bool,
        double_on: int | None,
        count_ones: bool,
    ) -> RollResult:
        """Execute the pool roll and return a RollResult."""
