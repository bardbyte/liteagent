"""
Example 8: Pipeline (Sequential Multi-Agent)
==============================================

Chain agents so the output of one feeds into the next.
Each agent transforms the data one step further.

Use this when you need:
- Multi-step workflows (extract → analyze → report)
- Separation of concerns (each agent does one thing well)
- To build reliable data processing chains

Setup:
    pip install -e .
    # Make sure .env has CONFIG_PATH set (see setup.sh)
"""

import asyncio
from liteagent import Agent, Pipeline


# --- Step 1: Extract data from Looker ---
extractor = Agent(
    system_prompt=(
        "You extract raw data from Looker. "
        "Use the available tools to run the query the user asks for. "
        "Return the raw data results — do NOT analyze or summarize. "
        "Include the SQL that was generated."
    ),
    tools=["conversational-analytics", "query", "query-sql"],
)

# --- Step 2: Analyze the data ---
analyst = Agent(
    system_prompt=(
        "You are a senior data analyst. You receive raw data results from Looker. "
        "Analyze the data and identify:\n"
        "- Key trends and patterns\n"
        "- Notable outliers or anomalies\n"
        "- Comparisons and rankings\n"
        "- Business implications\n"
        "Be specific — cite actual numbers from the data."
    ),
    # No tools — just LLM reasoning on the previous agent's output
)

# --- Step 3: Write an executive summary ---
writer = Agent(
    system_prompt=(
        "You write concise executive summaries for business stakeholders. "
        "You receive a data analysis. Write a 3-paragraph summary:\n"
        "1. Key finding (one sentence, the headline)\n"
        "2. Supporting details (2-3 bullets with numbers)\n"
        "3. Recommended action (what should leadership do?)\n"
        "Write for a VP audience — clear, no jargon, actionable."
    ),
    # No tools — just LLM writing
)


# --- Build the pipeline ---
pipeline = Pipeline(steps=[extractor, analyst, writer])


async def main():
    # Run the full pipeline
    result = await pipeline.run(
        "Revenue by product category for the last quarter, compared to previous quarter"
    )

    print("EXECUTIVE SUMMARY")
    print("=" * 60)
    print(result.content)
    print("=" * 60)

    # Inspect intermediate results
    print(f"\nPipeline stats:")
    print(f"  Total iterations: {result.iterations}")
    print(f"  Total tool calls: {len(result.tool_calls)}")
    print(f"  Tools used: {result.tools_used}")

    print(f"\nStep-by-step:")
    step_names = ["Extractor", "Analyst", "Writer"]
    for i, (name, step_result) in enumerate(
        zip(step_names, pipeline.intermediate_results)
    ):
        print(f"\n  [{name}]")
        print(f"  Iterations: {step_result.iterations}")
        print(f"  Tools: {step_result.tools_used}")
        print(f"  Output preview: {step_result.content[:100]}...")


    # --- Pipeline with custom transforms between steps ---
    pipeline_with_transforms = Pipeline(
        steps=[extractor, analyst, writer],
        transforms=[
            None,  # first step gets the raw user prompt
            lambda data: f"Analyze this Looker data:\n\n{data}",  # prefix for analyst
            lambda analysis: f"Write a summary of:\n\n{analysis}",  # prefix for writer
        ],
    )

    result = await pipeline_with_transforms.run("Top 10 customers by total spend")
    print(f"\n\nWith transforms:\n{result.content}")


if __name__ == "__main__":
    asyncio.run(main())
