# Claude Router

Claude Router is a local, Claude-compatible proxy for routing requests to Ollama and remote AI providers. It exposes an Anthropic-compatible `/v1/messages` endpoint for Claude clients and an OpenAI-compatible `/v1/chat/completions` endpoint for other clients.

The router currently supports:

- Ollama models discovered from `/api/tags`.
- Gemini models discovered from the Google Generative Language API.
- AgentRouter models discovered from its OpenAI-compatible `/v1/models` endpoint.
- Concurrent startup health checks.
- Automatic API-key rotation for cloud providers.
- Local Ollama fallback when a cloud request fails.
- Dynamic `.env.json` configuration reloads.
- Healthy and unavailable model reporting through `/v1/models`.

## Requirements

- macOS, Linux, or Windows
- Python 3.14 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Ollama, if local models or fallback behavior are required

## Install

Clone the repository and install the project dependencies:

```bash
uv sync
```

Once the project is published to PyPI, install the command-line application with
the hosted installer:

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.sh | sh
```

Build and publish a release with:

```bash
uv build
uv publish
```

Before publishing to PyPI, the installer can target a Git repository instead:

```bash
CLAUDE_ROUTER_PACKAGE="git+https://github.com/<owner>/<repo>.git" \\
	sh -c 'curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.sh | sh'
```

The installer installs `claude-router` as a `uv` tool and creates a user
configuration file at:

```text
~/.config/claude-router/config.json
```

Set `XDG_CONFIG_HOME` to use a different configuration directory, or set
`CLAUDE_ROUTER_CONFIG` to point to a specific JSON file. When running from a
checkout, a project-local `.env.json` takes precedence if it exists.

Install development dependencies, including pytest:

```bash
uv sync --dev
```

## Configuration

Copy the sample configuration to the project root:

```bash
cp .env.json.sample .env.json
```

Edit `.env.json` and add your provider credentials to the `API_KEYS` arrays. The file is ignored by Git and must never be committed.

```json
{
	"GEMINI": {
		"base_url": "https://generativelanguage.googleapis.com",
		"discovery_path": "/v1/models",
		"params": {
			"key": "${API_KEY}"
		},
		"API_KEYS": [
			"your-gemini-api-key"
		]
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
		"API_KEYS": [
			"your-agentrouter-api-key"
		]
	},
	"OLLAMA": {
		"base_url": "http://localhost:11434",
		"discovery_path": "/api/tags"
	},
	"DEFAULT_LOCAL_FALLBACK_MODEL": "llama3"
}
```

`API_KEYS` may contain multiple keys. The router shuffles the configured keys and retries another key after provider failures.

The router also accepts environment-variable overrides, but `.env.json` is the recommended configuration source:

```bash
export GEMINI_BASE_URL="https://generativelanguage.googleapis.com"
export DEFAULT_LOCAL_FALLBACK_MODEL="llama3"
```

## Start the Router

Start the server with the project command:

```bash
uv run claude-router
```

The default address is:

```text
http://127.0.0.1:8000
```

Startup performs provider discovery and concurrent health checks. The server logs show which models are healthy and which are unavailable:

```text
Healthy models: llama3.2:3b, gemini-3.5-flash
Unhealthy models: unavailable models are exposed with a prefix in /v1/models
```

Configuration changes are detected while the process is running. The model health cache is refreshed when `.env.json` changes.

## Use with Claude Code

Start the router in one terminal:

```bash
uv run claude-router
```

In another terminal, point Claude Code at the local Anthropic-compatible endpoint:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
export ANTHROPIC_AUTH_TOKEN="local-test"
claude
```

The router currently does not require the local token to match a configured value. It is supplied so Claude Code sends an authentication header in the normal way.

To use these settings for one command only:

```bash
ANTHROPIC_BASE_URL="http://127.0.0.1:8000" \
ANTHROPIC_AUTH_TOKEN="local-test" \
claude
```

Choose a model that appears without the `unavailable/` prefix. Models with that prefix are visible for status and discovery, but requests using them return HTTP `503` until their health check succeeds.

## API Endpoints

### List models

```bash
curl http://127.0.0.1:8000/v1/models
```

Healthy models are listed first. Unhealthy models are listed after them with the `unavailable/` prefix.

### Anthropic-compatible messages

```bash
curl http://127.0.0.1:8000/v1/messages \
	-H "Content-Type: application/json" \
	-H "x-api-key: local-test" \
	-H "anthropic-version: 2023-06-01" \
	-d '{
		"model": "gemini-3.5-flash",
		"max_tokens": 128,
		"stream": false,
		"messages": [
			{
				"role": "user",
				"content": "Explain how AI works in a few words."
			}
		]
	}'
```

### OpenAI-compatible chat completions

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
	-H "Content-Type: application/json" \
	-d '{
		"model": "llama3.2:3b",
		"messages": [
			{
				"role": "user",
				"content": "Hi"
			}
		],
		"stream": false
	}'
```

## Routing Behavior

1. The request model is matched against healthy local and discovered cloud models.
2. Anthropic messages are normalized into the router's internal OpenAI-style representation.
3. Gemini requests are converted into Gemini's native `contents` and `generationConfig` format.
4. Provider responses are normalized back into Anthropic or OpenAI format.
5. If a cloud request fails, the model is marked unhealthy and the request may fall back to the configured Ollama model.
6. A background worker retries unhealthy models and makes recovered models available again.

AgentRouter models are discovered from `/v1/models` and routed through `/v1/chat/completions`. Gemini uses the native `v1/models/{model}:generateContent` endpoint.

## Streaming Status

The API accepts `"stream": true`, but streaming is not yet equivalent across all providers.

- Ollama and OpenAI-compatible providers have a partial SSE path.
- Gemini requires its native `streamGenerateContent` endpoint and provider-specific chunk conversion.
- The current streaming implementation should be treated as experimental until provider-specific streaming tests are added.

Use non-streaming requests for the most predictable behavior:

```json
{
	"stream": false
}
```

## Tests and Lint

Run the test suite:

```bash
uv run pytest
```

Run Ruff:

```bash
uv run ruff check .
```

The test suite covers configuration reloads, provider discovery, route resolution, format conversion, API validation, health behavior, and log secret redaction.

## Security

- Never commit `.env.json`.
- Never put API keys in source code, command history, or README examples.
- Rotate any key that has been pasted into a terminal transcript, issue, chat, or log.
- The router redacts configured credentials from application logs, but preventing secrets from being exposed is still the primary protection.

## Project Layout

```text
app/main.py                    FastAPI application and request gateway
src/claude_router/             CLI entry point
src/helpers/backends.py        Discovery, routing, health, and fallback logic
src/helpers/config.py          JSON configuration and reload handling
src/helpers/formatters.py      Anthropic/OpenAI/Gemini conversions
src/constants/                 Defaults and project paths
test/                          Pytest suite
.env.json.sample               Safe configuration template
```
