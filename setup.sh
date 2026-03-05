#!/usr/bin/env bash
# ============================================================================
# liteagent setup — get from zero to running in 2 minutes
# ============================================================================
#
# This script walks you through:
#   1. Creating a Python virtual environment
#   2. Installing liteagent and dependencies
#   3. Setting up your .env with CONFIG_PATH
#   4. Creating the SafeChain config YAML
#   5. Verifying everything works
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${BOLD}liteagent${NC} — SafeChain made simple                       ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "\n${BLUE}[$1/$TOTAL_STEPS]${NC} ${BOLD}$2${NC}"
    echo -e "${BLUE}$(printf '%.0s─' {1..55})${NC}"
}

print_ok() {
    echo -e "    ${GREEN}✓${NC} $1"
}

print_warn() {
    echo -e "    ${YELLOW}⚠${NC} $1"
}

print_err() {
    echo -e "    ${RED}✗${NC} $1"
}

TOTAL_STEPS=5

print_header

# ============================================================================
# Step 1: Python check
# ============================================================================
print_step 1 "Checking Python"

if command -v python3 &> /dev/null; then
    PYTHON=$(command -v python3)
    PY_VERSION=$($PYTHON --version 2>&1)
    print_ok "Found $PY_VERSION at $PYTHON"

    # Check version >= 3.10
    PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MINOR" -lt 10 ]; then
        print_err "Python 3.10+ required, found 3.$PY_MINOR"
        exit 1
    fi
else
    print_err "Python 3 not found. Install Python 3.10+ first."
    exit 1
fi

# ============================================================================
# Step 2: Virtual environment
# ============================================================================
print_step 2 "Setting up virtual environment"

VENV_DIR=".venv"

if [ -d "$VENV_DIR" ]; then
    print_ok "Virtual environment already exists at $VENV_DIR"
else
    echo -e "    Creating virtual environment..."
    $PYTHON -m venv $VENV_DIR
    print_ok "Created $VENV_DIR"
fi

# Activate
source "$VENV_DIR/bin/activate"
print_ok "Activated ($(which python))"

# Upgrade pip
pip install --upgrade pip --quiet
print_ok "pip upgraded"

# ============================================================================
# Step 3: Install liteagent
# ============================================================================
print_step 3 "Installing liteagent"

echo -e "    Installing package and dependencies..."
pip install -e . --quiet 2>&1 | tail -1 || true
print_ok "liteagent installed"

# Check if safechain is available
if python -c "import safechain" 2>/dev/null; then
    print_ok "safechain found"
else
    print_warn "safechain not installed — install from your internal registry:"
    echo -e "        pip install safechain"
fi

# Check if ee_config is available
if python -c "import ee_config" 2>/dev/null; then
    print_ok "ee_config found"
else
    print_warn "ee_config not installed — install from your internal registry:"
    echo -e "        pip install ee_config"
fi

# ============================================================================
# Step 4: Environment config
# ============================================================================
print_step 4 "Configuring environment"

ENV_FILE=".env"
CONFIG_YAML="config.yml"

# --- .env file ---
if [ -f "$ENV_FILE" ]; then
    print_ok ".env already exists"

    # Check for CONFIG_PATH
    if grep -q "CONFIG_PATH" "$ENV_FILE"; then
        CONFIG_PATH_VALUE=$(grep "CONFIG_PATH" "$ENV_FILE" | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        print_ok "CONFIG_PATH = $CONFIG_PATH_VALUE"
    else
        print_warn "CONFIG_PATH not found in .env"
        echo ""
        echo -e "    ${YELLOW}Add this to your .env:${NC}"
        echo -e "    ${BOLD}CONFIG_PATH=$CONFIG_YAML${NC}"
        echo ""
        read -p "    Add it now? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            echo "CONFIG_PATH=$CONFIG_YAML" >> "$ENV_FILE"
            print_ok "Added CONFIG_PATH to .env"
        fi
    fi
else
    echo -e "    Creating .env file..."
    cat > "$ENV_FILE" << 'ENVEOF'
# liteagent Environment Configuration
# Copy this file to .env and fill in your values

# ============================================================================
# CIBIS Authentication (Enterprise IdaaS)
# ============================================================================
CIBIS_CONSUMER_KEY=your-cibis-consumer-key
CIBIS_CONSUMER_SECRET=your-cibis-consumer-secret
CIBIS_CONFIGURATION_ID=your-cibis-configuration-id

# ============================================================================
# SafeChain Configuration
# ============================================================================
CONFIG_PATH=config.yml

# ============================================================================
# Looker MCP Configuration
# ============================================================================
LOOKER_INSTANCE_URL=https://yourcompany.looker.com
LOOKER_CLIENT_ID=your-looker-client-id
LOOKER_CLIENT_SECRET=your-looker-client-secret

# ============================================================================
# Optional Settings
# ============================================================================
LOG_LEVEL=INFO
ENVEOF
    print_ok "Created .env (fill in your CIBIS, Looker, and CONFIG_PATH values)"
fi

# --- SafeChain config YAML ---
if [ -f "$CONFIG_YAML" ]; then
    print_ok "$CONFIG_YAML already exists"
else
    echo ""
    echo -e "    ${YELLOW}Creating SafeChain config template...${NC}"
    echo -e "    This is the YAML that SafeChain reads via CONFIG_PATH."
    echo -e "    You need to fill in your MCP server URL."
    echo ""

    cat > "$CONFIG_YAML" << 'EOF'
# SafeChain configuration
# This is read by Config.from_env() via the CONFIG_PATH env var.
#
# Fill in your MCP Toolbox server URL below.
# The Toolbox server handles Looker connectivity — this client just
# connects to it and loads whatever tools are available.

mcp:
  servers:
    looker:
      url: https://YOUR-TOOLBOX-SERVER.run.app
      transport: streamable-http
      # Optional: auth headers
      # headers:
      #   Authorization: "Bearer YOUR_TOKEN"

# Optional: model configuration
# model_id: gemini-2.0-flash
EOF

    print_ok "Created $CONFIG_YAML (template — fill in your MCP server URL)"
    print_warn "Edit $CONFIG_YAML with your actual Toolbox server URL before running"
fi

# --- Optional: liteagent.yaml ---
if [ ! -f "liteagent.yaml" ]; then
    cat > "liteagent.yaml" << 'EOF'
# liteagent settings (optional — everything has defaults)
# This is NOT the SafeChain config. SafeChain config comes from CONFIG_PATH.

model_id: gemini-pro       # default model for agents
max_iterations: 15          # max ReAct loop iterations
history_limit: 40           # max messages in chat history
EOF
    print_ok "Created liteagent.yaml (optional settings)"
fi

# ============================================================================
# Step 5: Verify
# ============================================================================
print_step 5 "Verifying installation"

# Check imports
echo -e "    Testing imports..."

python -c "
import sys
errors = []

# Core liteagent
try:
    from liteagent import Agent, Chat, call, call_sync
    from liteagent import Router, Pipeline
    from liteagent import Result, ToolCall
    from liteagent import ConsoleCallback, ThinkingEvent
    from liteagent import LiteAgentConfig
    print('    ✓ liteagent imports OK')
except Exception as e:
    errors.append(f'liteagent: {e}')
    print(f'    ✗ liteagent: {e}')

# Config resolution
try:
    cfg = LiteAgentConfig.resolve()
    print(f'    ✓ Config resolved: model={cfg.model_id}, iterations={cfg.max_iterations}')
except Exception as e:
    print(f'    ⚠ Config: {e} (normal if no liteagent.yaml)')

# ADK (optional)
try:
    from liteagent import LiteAgent
    from google.adk.agents import BaseAgent
    print('    ✓ ADK integration available')
except ImportError:
    print('    ⚠ ADK not installed (optional — pip install liteagent[adk])')

# SafeChain (required)
try:
    from safechain.tools.mcp import MCPToolLoader, MCPToolAgent
    from ee_config.config import Config
    print('    ✓ SafeChain + ee_config available')
except ImportError as e:
    errors.append(f'safechain/ee_config: {e}')
    print(f'    ✗ SafeChain/ee_config not installed — required: {e}')
    print('        pip install safechain ee_config')

if errors:
    sys.exit(1)
" || true

# Check CLI
if command -v liteagent &> /dev/null; then
    print_ok "CLI command 'liteagent' available"
else
    print_warn "CLI not in PATH — run: pip install -e ."
fi

# ============================================================================
# Done!
# ============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  ${BOLD}Setup complete!${NC}                                        ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo ""
echo -e "  1. ${YELLOW}Edit .env${NC} with your CIBIS, Looker, and CONFIG_PATH values
     ${YELLOW}Edit config.yml${NC} with your MCP Toolbox server URL"
echo ""
echo -e "  2. ${YELLOW}Activate the venv${NC} in each new terminal:"
echo -e "     source .venv/bin/activate"
echo ""
echo -e "  3. ${YELLOW}Try it out:${NC}"
echo -e "     python examples/01_one_shot_call.py    # simplest"
echo -e "     python examples/02_agent_basic.py      # agent with tools"
echo -e "     python examples/09_chat.py             # interactive chat"
echo -e "     liteagent --system 'You are a Looker expert'  # CLI"
echo ""
echo -e "  4. ${YELLOW}Read the examples:${NC}"
echo -e "     examples/01_one_shot_call.py       One-shot LLM call"
echo -e "     examples/02_agent_basic.py         Basic agent"
echo -e "     examples/03_tool_scoping.py        Tool scoping"
echo -e "     examples/04_structured_output.py   Typed responses"
echo -e "     examples/05_guardrails.py          Input/output validation"
echo -e "     examples/06_streaming.py           Real-time events"
echo -e "     examples/07_router.py              Multi-agent routing"
echo -e "     examples/08_pipeline.py            Sequential pipeline"
echo -e "     examples/09_chat.py                Interactive chat"
echo -e "     examples/10_adk_integration.py     Google ADK"
echo -e "     examples/11_retry_and_error_handling.py  Error handling"
echo ""
echo -e "  ${BOLD}Questions?${NC} Check README.md or ask in the team Slack."
echo ""
