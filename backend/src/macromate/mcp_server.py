"""MacroMate's self-hosted MCP server (Streamable HTTP).

Scope note: these tools are deliberately limited to *pure* calculations that the
project handoff already fully specifies. The stateful domain tools -- pantry,
cooking sessions, meal logs -- are blocked on the Kiro spec and must not be
invented here. See AGENTS.md, "Spec workflow".

Every tool below is deterministic Python. That is the point: the model decides
*which* tool to call and with what arguments; it never computes the numbers.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from macromate import __version__
from macromate.nutrition import Macros, remaining_against_targets, split_batch

mcp_server = MCPServer(
    name="macromate",
    title="MacroMate",
    version=__version__,
    instructions=(
        "Nutrition tools for cooking and meal prep. Call these for every "
        "calculation; do not compute calories or protein yourself. A result "
        "marked estimated=true is based on an unconfirmed quantity or an "
        "ambiguous product match -- say so when reporting it to the user."
    ),
)


@mcp_server.tool()
def calculate_portions(
    total_calories: Annotated[float, Field(ge=0, description="Batch total calories")],
    total_protein_g: Annotated[float, Field(ge=0, description="Batch total protein in grams")],
    portions: Annotated[int, Field(ge=1, description="How many servings to divide into")],
    estimated: Annotated[
        bool,
        Field(description="True if the batch totals came from a guess or unconfirmed amount"),
    ] = False,
) -> dict[str, float | int | bool]:
    """Divide a cooked batch into equal portions and report the macros per portion.

    Use for requests like "split that into four lunches". Reports what one
    serving contains; it does not log anything as eaten.
    """
    batch = Macros(calories=total_calories, protein_g=total_protein_g, estimated=estimated)
    portion = split_batch(batch, portions)
    return {
        "portions": portions,
        "calories_per_portion": portion.calories,
        "protein_g_per_portion": portion.protein_g,
        "batch_calories": batch.calories,
        "batch_protein_g": batch.protein_g,
        "estimated": portion.estimated,
    }


@mcp_server.tool()
def remaining_daily_targets(
    calorie_target: Annotated[float, Field(ge=0, description="Daily calorie goal")],
    protein_target_g: Annotated[float, Field(ge=0, description="Daily protein goal in grams")],
    consumed_calories: Annotated[float, Field(ge=0, description="Calories actually eaten today")],
    consumed_protein_g: Annotated[float, Field(ge=0, description="Protein actually eaten today")],
    estimated: Annotated[
        bool, Field(description="True if any consumed figure is an estimate")
    ] = False,
) -> dict[str, float | bool]:
    """Report calories and protein remaining against today's targets.

    Pass only food the user has actually *eaten*. Food that has been cooked but
    not eaten does not count -- preparing a batch is not consuming it.
    """
    return remaining_against_targets(
        calorie_target=calorie_target,
        protein_target_g=protein_target_g,
        consumed=Macros(
            calories=consumed_calories, protein_g=consumed_protein_g, estimated=estimated
        ),
    )


@mcp_server.tool()
def scale_ingredient(
    calories: Annotated[float, Field(ge=0, description="Calories at the original amount")],
    protein_g: Annotated[float, Field(ge=0, description="Protein at the original amount")],
    factor: Annotated[float, Field(ge=0, description="Multiplier: 0.5 for half, 2 for double")],
    estimated: Annotated[
        bool, Field(description="True if the original figures are estimates")
    ] = False,
) -> dict[str, float | bool]:
    """Rescale one ingredient's contribution after a mid-cook correction.

    Use for "actually, I only used half the rice". Returns the corrected
    contribution for that ingredient; the caller re-totals the batch.
    """
    scaled = Macros(calories=calories, protein_g=protein_g, estimated=estimated).scaled(factor)
    return {
        "calories": scaled.calories,
        "protein_g": scaled.protein_g,
        "factor": factor,
        "estimated": scaled.estimated,
    }
