"""
Degree-of-success Strategy implementations.

Each game system has its own algorithm for interpreting roll results
into degrees of success. The Strategy Pattern lets us swap these
without touching the roller logic.
"""

from .base import DegreeStrategy


class CoCDegreeStrategy(DegreeStrategy):
    """Call of Cthulhu 7e: Regular / Hard / Extreme / Critical / Fumble."""

    @property
    def name(self) -> str:
        return "coc"

    @property
    def requires_target(self) -> bool:
        return True

    def calculate(
        self,
        total: int,
        target: int | None = None,
        natural_value: int | None = None,
        critical: bool = False,
    ) -> list[str]:
        assert target is not None
        hard = target // 2
        extreme = target // 5
        lines: list[str] = []

        if total == 1:
            lines.append("Check: Critical! (01)")
        elif total <= extreme:
            lines.append(f"Check: Extreme Success! ({total} ≤ {extreme})")
        elif total <= hard:
            lines.append(f"Check: Hard Success! ({total} ≤ {hard})")
        elif total <= target:
            lines.append(f"Check: Regular Success ({total} ≤ {target})")
        elif (target <= 50 and total >= 96) or total == 100:
            lines.append(f"Check: Fumble! ({total})")
        else:
            lines.append(f"Check: Failure ({total} > {target})")

        lines.append(f"  [Regular ≤{target} / Hard ≤{hard} / Extreme ≤{extreme}]")
        return lines


class PF2eDegreeStrategy(DegreeStrategy):
    """Pathfinder 2e: margin-based degrees with nat 20/1 shift."""

    @property
    def name(self) -> str:
        return "pf2e"

    @property
    def requires_target(self) -> bool:
        return True

    def calculate(
        self,
        total: int,
        target: int | None = None,
        natural_value: int | None = None,
        critical: bool = False,
    ) -> list[str]:
        assert target is not None

        # Base degree by margin
        if total >= target + 10:
            degree = "crit_success"
        elif total >= target:
            degree = "success"
        elif total > target - 10:
            degree = "failure"
        else:
            degree = "crit_failure"

        # Nat 20/1 shifts degree by one step
        nat_shift = ""
        if critical and natural_value is not None:
            upgrades = {
                "crit_failure": "failure",
                "failure": "success",
                "success": "crit_success",
            }
            downgrades = {
                "crit_success": "success",
                "success": "failure",
                "failure": "crit_failure",
            }
            if natural_value == 20 and degree in upgrades:
                degree = upgrades[degree]
                nat_shift = " (Nat 20 ↑)"
            elif natural_value == 1 and degree in downgrades:
                degree = downgrades[degree]
                nat_shift = " (Nat 1 ↓)"

        labels = {
            "crit_success": "Critical Success!",
            "success": "Success",
            "failure": "Failure",
            "crit_failure": "Critical Failure!",
        }
        margin = total - target
        sign = "+" if margin >= 0 else ""
        return [
            f"Check: {labels[degree]}{nat_shift} (margin: {sign}{margin})",
            f"  [DC {target}: Crit ≥{target + 10} / Pass ≥{target} / Crit Fail ≤{target - 10}]",
        ]


class PbtADegreeStrategy(DegreeStrategy):
    """Powered by the Apocalypse: Strong Hit / Weak Hit / Miss."""

    @property
    def name(self) -> str:
        return "pbta"

    @property
    def requires_target(self) -> bool:
        return False

    def calculate(
        self,
        total: int,
        target: int | None = None,
        natural_value: int | None = None,
        critical: bool = False,
    ) -> list[str]:
        if total >= 10:
            line = f"Check: Strong Hit! ({total} ≥ 10)"
        elif total >= 7:
            line = f"Check: Weak Hit ({total}: 7-9)"
        else:
            line = f"Check: Miss ({total} ≤ 6)"
        return [line, "  [Strong ≥10 / Weak 7-9 / Miss ≤6]"]


# --- Strategy Registry ---
# Maps degree system names to strategy instances.
# Open/Closed Principle: add new systems by registering, not modifying.

DEGREE_REGISTRY: dict[str, DegreeStrategy] = {
    "coc": CoCDegreeStrategy(),
    "pf2e": PF2eDegreeStrategy(),
    "pbta": PbtADegreeStrategy(),
}
