"""Tests for the deterministic nutrition layer."""

from __future__ import annotations

import pytest

from macromate.nutrition import (
    Macros,
    NutritionError,
    remaining_against_targets,
    split_batch,
    total,
)


def test_handoff_worked_example() -> None:
    """The exact example from the project handoff: 1800/150 split four ways."""
    batch = Macros(calories=1800, protein_g=150)
    portion = split_batch(batch, 4)
    assert portion.calories == 450
    assert portion.protein_g == 37.5


def test_split_rejects_zero_portions() -> None:
    with pytest.raises(NutritionError):
        split_batch(Macros(calories=100, protein_g=10), 0)


def test_estimated_flag_is_contagious_through_addition() -> None:
    confirmed = Macros(calories=100, protein_g=10)
    guessed = Macros(calories=50, protein_g=5, estimated=True)
    assert (confirmed + guessed).estimated is True


def test_estimated_flag_survives_scaling() -> None:
    """Scaling an estimate must not launder it into a confirmed number."""
    assert Macros(calories=100, protein_g=10, estimated=True).scaled(0.5).estimated is True


def test_unknown_macro_stays_unknown_rather_than_zero() -> None:
    """None means 'we do not know', which is not the same as 'none present'."""
    known = Macros(calories=100, protein_g=10, carbs_g=20, fat_g=5)
    partial = Macros(calories=50, protein_g=5, carbs_g=None, fat_g=2)
    combined = known + partial
    assert combined.carbs_g is None
    assert combined.fat_g == 7


def test_mid_cook_correction_halves_the_batch() -> None:
    """'Actually, I used half as much rice.'"""
    rice = Macros(calories=600, protein_g=12)
    assert rice.scaled(0.5).calories == 300


def test_total_of_empty_batch_is_zero_and_confirmed() -> None:
    empty = total([])
    assert empty.calories == 0
    assert empty.estimated is False


def test_negative_macros_rejected() -> None:
    with pytest.raises(NutritionError):
        Macros(calories=-1, protein_g=0)


def test_remaining_targets_reports_overage_rather_than_clamping() -> None:
    result = remaining_against_targets(
        calorie_target=2000,
        protein_target_g=150,
        consumed=Macros(calories=2200, protein_g=160),
    )
    assert result["calories_remaining"] == -200
    assert result["calories_over_target"] is True
    assert result["protein_target_met"] is True
