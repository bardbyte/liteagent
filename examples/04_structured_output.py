"""
Example 4: Structured Output
==============================

Get typed, validated responses from the LLM using Pydantic models.
Instead of parsing free-text, you get a Python object back.

Use this when you need:
- JSON responses for downstream processing
- Type-safe LLM outputs in data pipelines
- To feed LLM results into other systems (APIs, databases, UIs)

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import asyncio
from pydantic import BaseModel, Field
from liteagent import Agent


# --- Define your output schemas ---

class LookerModel(BaseModel):
    """A Looker model with its explores."""
    name: str
    explores: list[str]
    description: str = ""


class SchemaReport(BaseModel):
    """Summary of available Looker schema."""
    models: list[LookerModel]
    total_explores: int
    recommended_model: str = Field(description="Best model for general analytics")


class QueryPlan(BaseModel):
    """Plan for executing a data query."""
    model: str
    explore: str
    dimensions: list[str]
    measures: list[str]
    filters: dict[str, str] = Field(default_factory=dict)
    reasoning: str = Field(description="Why these fields were chosen")


class SensitivityReport(BaseModel):
    """PII/sensitivity classification of fields."""
    field_name: str
    sensitivity_level: str = Field(description="CM15, CM11, or none")
    contains_pii: bool
    reasoning: str


async def main():
    agent = Agent(
        system_prompt="You are a Looker analytics expert.",
        tools=["get-models", "get-explores", "get-dimensions", "get-measures"],
    )

    # --- Get schema as a typed object ---
    result = await agent.run(
        "List all available Looker models with their explores",
        output_type=SchemaReport,
    )

    if result.parsed:
        report: SchemaReport = result.parsed
        print(f"Found {len(report.models)} models, {report.total_explores} explores")
        print(f"Recommended: {report.recommended_model}")
        for model in report.models:
            print(f"  {model.name}: {', '.join(model.explores)}")
    else:
        # Parsing failed — fall back to raw content
        print(f"Could not parse structured output. Raw: {result.content[:200]}")

    # --- Build a query plan ---
    result = await agent.run(
        "Plan a query to get total revenue by product category for last quarter",
        output_type=QueryPlan,
    )

    if result.parsed:
        plan: QueryPlan = result.parsed
        print(f"\nQuery Plan:")
        print(f"  Model: {plan.model}")
        print(f"  Explore: {plan.explore}")
        print(f"  Dimensions: {plan.dimensions}")
        print(f"  Measures: {plan.measures}")
        print(f"  Filters: {plan.filters}")
        print(f"  Reasoning: {plan.reasoning}")


if __name__ == "__main__":
    asyncio.run(main())
