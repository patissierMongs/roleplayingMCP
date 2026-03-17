"""
Abstract Strategy interface for degree-of-success calculations.

Strategy Pattern: Define a family of algorithms, encapsulate each one,
and make them interchangeable. Only applied where it genuinely fits —
degree systems ARE interchangeable (CoC, PF2e, PbtA all answer the
same question: "given a total, what's the degree of success?").
"""

from abc import ABC, abstractmethod


class DegreeStrategy(ABC):
    """Strategy for calculating success degrees."""

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
