#!/bin/sh
set -eu

PACKAGE_SPEC="${CLAUDE_ROUTER_PACKAGE:-claude-router}"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/claude-router"
CONFIG_PATH="$CONFIG_DIR/config.json"

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

uv tool install --upgrade "$PACKAGE_SPEC"

mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_PATH" ]; then
    cat > "$CONFIG_PATH" <<'JSON'
{
  "GEMINI": {
    "base_url": "https://generativelanguage.googleapis.com",
    "discovery_path": "/v1/models",
    "params": {"key": "${API_KEY}"},
    "API_KEYS": []
  },
  "AGENTROUTER": {
    "base_url": "https://agentrouter.org",
    "discovery_path": "/v1/models",
    "headers": {
      "Accept": "application/json",
      "User-Agent": "Cline/3.0.0 (VSCode; Core)",
      "Origin": "vscode-file://vscode-app"
    },
    "auth_header": "Authorization",
    "auth_scheme": "Bearer",
    "API_KEYS": []
  },
  "OLLAMA": {
    "base_url": "http://localhost:11434",
    "discovery_path": "/api/tags"
  },
  "DEFAULT_LOCAL_FALLBACK_MODEL": "llama3"
}
JSON
fi

printf '%s\n' "Installed $PACKAGE_SPEC."
printf '%s\n' "Configure provider keys in $CONFIG_PATH"
printf '%s\n' "Run: claude-router"