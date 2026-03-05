# liteagent

**SafeChain made simple** — build LLM agents in 3 lines instead of 30.

```python
from liteagent import Agent

agent = Agent(system_prompt="You are a Looker analytics expert")
result = await agent.run("What models are available?")
```

That's it. No `Config.from_env()`. No `MCPToolLoader.load_tools()`. No message conversion. No ReAct loop. liteagent handles all of it.

---

## The Problem

Every developer on the team writes the same 30 lines of boilerplate to use SafeChain:

```python
# What you write TODAY to make one LLM call with tools:

import asyncio
from dotenv import load_dotenv, find_dotenv
from ee_config.config import Config
from safechain.tools.mcp import MCPToolLoader, MCPToolAgent
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(find_dotenv())
config = Config.from_env()
tools = await MCPToolLoader.load_tools(config)
model_id = (
    getattr(config, 'model_id', None)
    or getattr(config, 'model', None)
    or getattr(config, 'llm_model', None)
    or "gemini-pro"
)
agent = MCPToolAgent(model_id, tools)

messages = [
    SystemMessage(content="You are a Looker expert"),
    HumanMessage(content="What models are available?"),
]
raw = await agent.ainvoke(messages)

# And this is SINGLE-PASS. If you want a ReAct loop (multi-step reasoning),
# you need another 50+ lines: while loop, tool result parsing, message
# history management, error handling, retry logic...
```

Three different files in this repo (`chat.py`, `src/agent.py`, `augment_poc/enrichment_agent.py`) all repeat this same init dance. Every new developer copies it, tweaks it slightly, and introduces subtle bugs.

## The Solution

```python
from liteagent import Agent

agent = Agent(system_prompt="You are a Looker expert")
result = await agent.run("What models are available?")
print(result.content)
```

liteagent gives you:
- **Automatic bootstrap** — reads your `.env` and `config.yml` exactly like `chat.py` does
- **Built-in ReAct loop** — multi-step reasoning out of the box
- **Tool scoping** — each agent sees only the tools it needs
- **Guardrails** — validate inputs and outputs before/after LLM calls
- **Structured output** — parse responses into Pydantic models
- **Streaming** — get thinking events as they happen
- **Multi-agent patterns** — Router, Pipeline, Google ADK integration
- **Sync wrappers** — works in Jupyter, Streamlit, and scripts

Same SafeChain. Same `.env`. Same `config.yml`. Same MCP servers. Zero new infrastructure.

---

## Setup

### Quick start (2 minutes)

```bash
# Clone and install
cd liteagent
chmod +x setup.sh
./setup.sh
```

The setup script walks you through everything interactively.

### Manual setup

**1. Install**

```bash
pip install -e .
```

**2. Create your `.env`** (same format as the existing safechain project):

```bash
# .env

# CIBIS Authentication (Enterprise IdaaS)
CIBIS_CONSUMER_KEY=your-cibis-consumer-key
CIBIS_CONSUMER_SECRET=your-cibis-consumer-secret
CIBIS_CONFIGURATION_ID=your-cibis-configuration-id

# SafeChain Configuration
CONFIG_PATH=config.yml

# Looker MCP Configuration
LOOKER_INSTANCE_URL=https://yourcompany.looker.com
LOOKER_CLIENT_ID=your-looker-client-id
LOOKER_CLIENT_SECRET=your-looker-client-secret
```

**3. Create your `config.yml`** (the SafeChain config that `CONFIG_PATH` points to):

```yaml
mcp:
  servers:
    looker:
      url: https://your-toolbox-server.run.app
      transport: streamable-http
```

**4. Make sure your MCP Toolbox server is running.**

If you already have a working `chat.py` setup with `.env` and `config.yml`, liteagent will work with zero changes — it reads the exact same files.

---

## Three APIs

### 1. `call()` — One-shot LLM call

No tool loop, just prompt in, response out. Good for summarization, classification, formatting.

```python
from liteagent import call

result = await call("Summarize this data", system="You are a data analyst")
print(result)  # prints result.content
```

### 2. `Agent` — Agentic workflow with ReAct loop

The agent calls the LLM, executes tools, feeds results back, and loops until it has a final answer. This is what `chat.py`'s `AgentOrchestrator` does — but in 3 lines.

```python
from liteagent import Agent

agent = Agent(
    system_prompt="You are a Looker analytics expert",
    tools=["conversational-analytics", "get-models", "query"],
)
result = await agent.run("What's the total revenue by region for Q4?")

print(result.content)       # the final answer
print(result.tool_calls)    # what tools were used
print(result.iterations)    # how many ReAct loops it took
```

### 3. `Chat` — Interactive session with history

Multi-turn conversation with memory. Drop-in replacement for `chat.py`'s CLI.

```python
from liteagent import Chat

chat = Chat(system_prompt="You are a data analyst")
await chat.start()  # launches CLI with /tools, /clear, /help, /quit
```

Or from the command line:

```bash
liteagent --system "You are a Looker analytics expert"
liteagent --tools conversational-analytics get-models get-explores
```

### Sync variants

Every async API has a sync version for Jupyter, Streamlit, and scripts:

```python
from liteagent import call_sync, Agent, Chat

result = call_sync("hello", system="You are helpful")

agent = Agent(system_prompt="You are a Looker expert")
result = agent.run_sync("What models are available?")

chat = Chat(system_prompt="You are a data analyst")
chat.start_sync()
```

---

## Agent Patterns

### Tool Scoping

Restrict which MCP tools an agent can see. Essential for multi-agent systems.

```python
# This agent can ONLY use these 3 tools (out of 40+)
analyst = Agent(
    system_prompt="You analyze data using Looker",
    tools=["conversational-analytics", "query", "query-sql"],
)

# This agent explores schemas
explorer = Agent(
    system_prompt="You help users understand available data",
    tools=["get-models", "get-explores", "get-dimensions", "get-measures"],
)
```

If you request a tool that doesn't exist, you get a clear error listing all available tools.

### Guardrails

Validate inputs before the LLM sees them, and outputs before the user sees them:

```python
def block_destructive(prompt: str) -> str | None:
    """Return error message to block, or None to allow."""
    if any(w in prompt.lower() for w in ["delete", "drop", "destroy"]):
        return "Destructive operations are not allowed"
    return None

def no_pii_in_output(content: str) -> str | None:
    import re
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', content):
        return "Response contains potential PII"
    return None

agent = Agent(
    system_prompt="You are a data analyst",
    input_guardrails=[block_destructive],
    output_guardrails=[no_pii_in_output],
)

# This raises GuardrailError:
await agent.run("Delete all customer records")
```

### Structured Output

Parse LLM responses into typed Pydantic models:

```python
from pydantic import BaseModel

class ModelList(BaseModel):
    models: list[str]
    recommended: str

result = await agent.run("List all Looker models", output_type=ModelList)
print(result.parsed.models)       # ["ecommerce", "marketing", ...]
print(result.parsed.recommended)  # "ecommerce"
```

### Streaming

Get thinking events as they happen — for real-time UIs or logging:

```python
from liteagent import Agent, ThinkingType

agent = Agent(system_prompt="You are a Looker expert")

async for event in agent.stream("What models are available?"):
    if event.type == ThinkingType.TOOL_CALL:
        print(f"  Calling: {event.metadata['tool_name']}")
    elif event.type == ThinkingType.TOOL_RESULT:
        print(f"  Result: {event.content[:100]}")
    elif event.type == ThinkingType.FINAL_ANSWER:
        print(f"\nAnswer: {event.content}")
```

### Thinking Callbacks

Rich console output of agent reasoning (same as `chat.py`'s panels):

```python
from liteagent import Agent, ConsoleCallback

agent = Agent(
    system_prompt="You are a Looker expert",
    on_thinking=ConsoleCallback(use_rich=True),
)

# Or use a plain function:
agent = Agent(
    system_prompt="You are a Looker expert",
    on_thinking=lambda e: print(f"[{e.type.value}] {e.content[:80]}"),
)
```

### Retry on Error

Automatically retry when tool execution fails (network blips, transient MCP errors):

```python
agent = Agent(
    system_prompt="You are a Looker expert",
    max_retries=2,  # retry up to 2 times on error
)
```

---

## Multi-Agent Patterns

### Router

Route messages to the right specialist based on content:

```python
from liteagent import Agent, Router

analyst = Agent(
    system_prompt="You analyze data",
    tools=["query", "conversational-analytics"],
)
explorer = Agent(
    system_prompt="You explore schemas",
    tools=["get-models", "get-explores", "get-dimensions"],
)
general = Agent(system_prompt="You answer general questions")

def route(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ["model", "explore", "schema", "field"]):
        return "explorer"
    if any(w in msg for w in ["revenue", "sales", "total", "query"]):
        return "analyst"
    return "general"

router = Router(
    agents={"analyst": analyst, "explorer": explorer, "general": general},
    route=route,
    default="general",
)

result = await router.run("What models are available?")   # -> explorer
result = await router.run("Total revenue by region")       # -> analyst
```

### Pipeline

Chain agents — each agent's output feeds the next:

```python
from liteagent import Agent, Pipeline

extractor = Agent(
    system_prompt="Extract raw data from Looker. Return data as-is.",
    tools=["query", "conversational-analytics"],
)
analyst = Agent(
    system_prompt="Analyze the provided data. Find trends and anomalies.",
)
writer = Agent(
    system_prompt="Write a concise executive summary.",
)

pipe = Pipeline(steps=[extractor, analyst, writer])
result = await pipe.run("Q4 revenue by region vs last year")

# result.content = executive summary
# result.tool_calls = all tools used across all 3 steps
# pipe.intermediate_results = [extractor_result, analyst_result, writer_result]
```

### Google ADK Integration

Use liteagent agents inside Google's Agent Development Kit for advanced orchestration:

```python
from liteagent import LiteAgent
from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.runners import InMemoryRunner

looker = LiteAgent(
    name="LookerAnalyst",
    description="Queries Looker semantic layer via MCP tools",
    system_prompt="You are a Looker analytics expert",
    tool_names=["conversational-analytics", "get-models", "query"],
)

pipeline = SequentialAgent(
    name="AnalyticsPipeline",
    sub_agents=[
        LlmAgent(name="Planner", model="gemini-2.5-flash",
                 instruction="Plan the analysis.", output_key="plan"),
        looker,
        LlmAgent(name="Summarizer", model="gemini-2.5-flash",
                 instruction="Summarize the findings."),
    ],
)

runner = InMemoryRunner(agent=pipeline)
```

Requires: `pip install liteagent[adk]`

---

## The Result Object

Every API returns a `Result` dataclass with everything you need:

```python
result = await agent.run("What models are available?")

result.content      # str — the final answer
result.tool_calls   # list[ToolCall] — every tool invocation
result.iterations   # int — how many ReAct loops
result.thinking     # list[ThinkingEvent] — full reasoning trace
result.parsed       # Any — structured output (if output_type was set)
result.tools_used   # list[str] — unique tool names used, in order
result.has_errors   # bool — did any tool call fail?
result.failed_tools # list[ToolCall] — which tools errored

str(result)         # returns result.content
bool(result)        # True if content is non-empty
```

Each `ToolCall`:

```python
tc = result.tool_calls[0]
tc.name     # "get-models"
tc.result   # "['ecommerce', 'marketing']"
tc.error    # "" (empty if ok)
tc.ok       # True
```

---

## Configuration

### SafeChain config (required — you already have this)

liteagent reads the same `.env` and `config.yml` that `chat.py` uses. If your existing setup works, liteagent works.

```
.env                  →  CONFIG_PATH=config.yml
config.yml            →  mcp.servers with your Toolbox URL
```

The bootstrap flow is identical to `chat.py`:

```
load_dotenv()  →  Config.from_env()  →  MCPToolLoader.load_tools()  →  MCPToolAgent()
```

### liteagent settings (optional)

You can optionally create a `liteagent.yaml` to override defaults:

```yaml
# liteagent.yaml (optional — everything has sensible defaults)
model_id: gemini-pro       # default model for agents
max_iterations: 15          # max ReAct loop iterations per run
history_limit: 40           # max messages kept in chat history
```

Discovery order: explicit path > `$LITEAGENT_CONFIG` > `./liteagent.yaml` > `~/.config/liteagent/config.yaml` > built-in defaults.

---

## Examples

The `examples/` directory has 11 progressive examples covering every pattern:

| # | File | What it covers |
|---|------|----------------|
| 01 | `one_shot_call.py` | Simplest possible usage — `call()` |
| 02 | `agent_basic.py` | Agent with ReAct loop and tool execution |
| 03 | `tool_scoping.py` | Restricting tools per agent |
| 04 | `structured_output.py` | Pydantic-typed responses |
| 05 | `guardrails.py` | Input/output validation |
| 06 | `streaming.py` | Real-time thinking events |
| 07 | `router.py` | Multi-agent routing |
| 08 | `pipeline.py` | Sequential agent pipeline |
| 09 | `chat.py` | Interactive chat session |
| 10 | `adk_integration.py` | Google ADK orchestration |
| 11 | `retry_and_error_handling.py` | Retry logic and error recovery |

Start with `01` and work your way up.

---

## How It Works

liteagent is a thin wrapper around SafeChain. Here's what happens when you call `agent.run()`:

1. **First call triggers lazy bootstrap** (cached for the process):
   - `load_dotenv()` — loads your `.env`
   - `Config.from_env()` — reads `CONFIG_PATH` env var, loads your `config.yml`
   - `MCPToolLoader.load_tools(config)` — connects to MCP servers, loads tools
   - Tools are cached — multiple agents share one tool load

2. **Tool scoping** — if you specified `tools=["a", "b"]`, only those tools are passed to the LLM

3. **ReAct loop** — calls `MCPToolAgent.ainvoke()` in a loop:
   - LLM decides which tool to call
   - Tool is executed, result is added to message history
   - Loop continues until LLM gives a final answer (no tool calls)
   - Stops at `max_iterations` as a safety net

4. **Result** — returns a `Result` with content, tool calls, iterations, and thinking trace

This is the same flow as `chat.py`'s `AgentOrchestrator`, extracted into a reusable package.

---

## Package Structure

```
src/liteagent/
├── __init__.py        # Public API — import everything from here
├── _agent.py          # Agent class with ReAct loop
├── _call.py           # call() — one-shot LLM call
├── _chat.py           # Chat class + CLI entry point
├── _multi.py          # Router and Pipeline
├── _adk.py            # Google ADK adapter (LiteAgent)
├── _bootstrap.py      # Lazy cached init: .env → Config → tools
├── _config.py         # liteagent.yaml discovery + parsing
├── _result.py         # Result and ToolCall dataclasses
├── _thinking.py       # ThinkingEvent, ConsoleCallback
├── _errors.py         # ConfigNotFoundError, BootstrapError, GuardrailError
├── _sync.py           # Sync wrappers for Jupyter/Streamlit
└── py.typed           # PEP 561 marker
```

## Dependencies

| Package | Why |
|---------|-----|
| `safechain` | LLM access + MCP tool binding (required) |
| `ee_config` | Enterprise config loader (required) |
| `langchain-core==0.3.83` | Message types for LangChain |
| `langchain-mcp-adapter==2.1.7` | MCP protocol support |
| `python-dotenv` | `.env` file loading |
| `pyyaml` | YAML config parsing |
| `rich` | Console output formatting |
| `pydantic` | Structured output + ADK compatibility |
| `google-adk` | ADK integration (optional: `pip install liteagent[adk]`) |
