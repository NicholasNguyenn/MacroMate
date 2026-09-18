"""Deterministic nutrition arithmetic.

This module exists because of AGENTS.md invariant 2: **the LLM never does
arithmetic**. Every number a user sees is computed here, from confirmed
quantities, by ordinary Python.

Invariant 3 -- uncertainty stays visible -- is enforced structurally: `Macros`
carries an `estimated` flag that propagates through every operation. Combine a
confirmed value with an estimated one and the result is estimated. There is no
way to launder an estimate into a confirmed number by doing math on it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


class NutritionError(ValueError):
    """Raised when a calculation is asked for something that has no valid answer."""


@dataclass(frozen=True, slots=True)
class Macros:
    """A bundle of macronutrients.

    `estimated` marks values that came from a guess, an unconfirmed quantity, or
    an ambiguous product match, rather than from a confirmed lookup.
    """

    calories: float
    protein_g: float
    carbs_g: float | None = None
    fat_g: float | None = None
    estimated: bool = False

    def __post_init__(self) -> None:
        for field in ("calories", "protein_g", "carbs_g", "fat_g"):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise NutritionError(f"{field} cannot be negative (got {value})")

    def __add__(self, other: Macros) -> Macros:
        return Macros(
            calories=self.calories + other.calories,
            protein_g=self.protein_g + other.protein_g,
            carbs_g=_add_optional(self.carbs_g, other.carbs_g),
            fat_g=_add_optional(self.fat_g, other.fat_g),
            # Uncertainty is contagious.
            estimated=self.estimated or other.estimated,
        )

    def scaled(self, factor: float) -> Macros:
        """Scale by `factor`. Used when a user corrects a quantity mid-cook."""
        if factor < 0:
            raise NutritionError(f"scale factor cannot be negative (got {factor})")
        return Macros(
            calories=self.calories * factor,
            protein_g=self.protein_g * factor,
            carbs_g=_scale_optional(self.carbs_g, factor),
            fat_g=_scale_optional(self.fat_g, factor),
            estimated=self.estimated,
        )

    def as_estimated(self) -> Macros:
        return replace(self, estimated=True)


def _add_optional(a: float | None, b: float | None) -> float | None:
    """Sum two optional values. Unknown + known stays unknown, never 0 + known."""
    if a is None or b is None:
        return None
    return a + b


def _scale_optional(value: float | None, factor: float) -> float | None:
    return None if value is None else value * factor


def total(components: list[Macros]) -> Macros:
    """Total a batch. An empty batch is zero, and is not an estimate."""
    running = Macros(calories=0.0, protein_g=0.0, carbs_g=0.0, fat_g=0.0)
    for component in components:
        running = running + component
    return running


def split_batch(batch: Macros, portions: int) -> Macros:
    """Divide a cooked batch into `portions` equal servings.

    The handoff's worked example: a batch of 1800 kcal / 150 g protein split four
    ways gives 450 kcal / 37.5 g protein per portion.
    """
    if portions < 1:
        raise NutritionError(f"portions must be at least 1 (got {portions})")
    return batch.scaled(1.0 / portions)


def remaining_against_targets(
    *,
    calorie_target: float,
    protein_target_g: float,
    consumed: Macros,
) -> dict[str, float | bool]:
    """Remaining daily allowance after what has actually been eaten.

    Only *consumed* food counts here. Cooking a batch is not eating it
    (AGENTS.md invariant 1), so callers must pass Consumed totals -- never
    Prepared ones.

    Values may go negative; that is a real state (over target) and is reported
    rather than clamped.
    """
    if calorie_target < 0 or protein_target_g < 0:
        raise NutritionError("daily targets cannot be negative")
    return {
        "calories_remaining": calorie_target - consumed.calories,
        "protein_g_remaining": protein_target_g - consumed.protein_g,
        "calories_over_target": consumed.calories > calorie_target,
        "protein_target_met": consumed.protein_g >= protein_target_g,
        "estimated": consumed.estimated,
    }
