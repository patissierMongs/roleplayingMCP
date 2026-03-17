"""
Strategy Pattern — degree-of-success calculations only.

DegreeStrategy is the one place Strategy genuinely fits:
multiple interchangeable algorithms answering the same question
("given a total, what's the degree of success?"), selected at
runtime via registry lookup.
"""

from .base import DegreeStrategy
from .degrees import CoCDegreeStrategy, PF2eDegreeStrategy, PbtADegreeStrategy, DEGREE_REGISTRY

__all__ = [
    "DegreeStrategy",
    "CoCDegreeStrategy",
    "PF2eDegreeStrategy",
    "PbtADegreeStrategy",
    "DEGREE_REGISTRY",
]
