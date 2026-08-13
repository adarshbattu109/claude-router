import os
from pathlib import Path

PROJECT_ROOT = Path.cwd()
LOCAL_CONFIG_PATH = PROJECT_ROOT / ".env.json"
USER_CONFIG_PATH = (
	Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
	/ "claude-router"
	/ "config.json"
)
CONFIG_PATH = Path(
	os.getenv(
		"CLAUDE_ROUTER_CONFIG",
		str(LOCAL_CONFIG_PATH if LOCAL_CONFIG_PATH.exists() else USER_CONFIG_PATH),
	)
)
