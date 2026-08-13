# Contributing

Thank you for contributing to Claude Router.

## Getting Started

```bash
git clone https://github.com/adarshbattu109/claude-router.git
cd claude-router
uv sync --dev
cp .env.json.sample .env.json
```

Provider credentials are not required for the test suite. Do not commit `.env.json` or real API keys.

## Development Workflow

1. Create a branch from `main`.
2. Make a focused change.
3. Add or update tests for behavior changes.
4. Run the checks below.
5. Open a pull request against `main`.

## Running Checks

```bash
uv run pytest
uv run ruff check .
uv build
```

Tests must not require live provider credentials or network access. Mock provider calls in tests.

## Pull Requests

- Keep pull requests focused and explain the behavior changed.
- Include tests for new behavior.
- Update the README when configuration or user-facing behavior changes.
- Never include credentials, generated build artifacts, or local configuration.
- Confirm CI passes before requesting review.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat: add provider discovery
fix: handle unavailable fallback models
docs: explain Claude Code setup
test: cover Gemini response conversion
ci: add dependency auditing
```

## Design Notes

Provider-specific wire formats belong in `src/helpers/formatters.py` and provider transport/discovery belongs in `src/helpers/backends.py`. Keep the public Anthropic and OpenAI-compatible API shapes stable.
