import json
import os
import random

from constants import constants
from constants.filepaths import CONFIG_PATH


def _load_config() -> dict:
    try:
        with CONFIG_PATH.open(encoding="utf-8") as config_file:
            data = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


_FILE_CONFIG = {}
_CONFIG_MTIME_NS = None
CONFIG_VERSION = 0


def _get_config_value(name: str, default: str = "") -> str:
    _refresh_file_config()
    value = os.getenv(name, _FILE_CONFIG.get(name, default))
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value)



def _provider_value(provider: str, name: str, default):
    provider_config = _FILE_CONFIG.get(provider, {})
    if isinstance(provider_config, dict) and name in provider_config:
        return provider_config[name]
    return _FILE_CONFIG.get(f"{provider}_{name.upper()}", default)


def _provider_urls(provider: str, default: str) -> list[str]:
    value = _provider_value(provider, "base_url", default)
    if isinstance(value, list):
        return [str(url).strip() for url in value if str(url).strip()]
    return [url.strip() for url in str(value).split(",") if url.strip()]


def get_provider_settings(provider: str) -> dict:
    """Return a provider's JSON settings with environment overrides applied."""
    _refresh_file_config()
    defaults = {
        "OLLAMA": {"discovery_path": "/api/tags"},
        "GEMINI": {
            "discovery_path": f"/{constants.GEMINI_API_VERSION}/models",
            "params": {"key": "${API_KEY}"},
        },
        "AGENTROUTER": {
            "discovery_path": "/v1/models",
            "headers": {
                "Accept": "application/json",
                "User-Agent": "Cline/3.0.0 (VSCode; Core)",
                "Origin": "vscode-file://vscode-app",
            },
            "auth_header": "Authorization",
            "auth_scheme": "Bearer",
        },
    }
    settings = {**defaults.get(provider, {}), **_FILE_CONFIG.get(provider, {})}
    settings["base_url"] = os.getenv(
        f"{provider}_BASE_URL", settings.get("base_url", "")
    )
    settings["API_KEYS"] = get_shuffled_keys(provider.lower())
    return settings

def _refresh_file_config() -> None:
    global _CONFIG_MTIME_NS, _FILE_CONFIG, CONFIG_VERSION

    try:
        mtime_ns = CONFIG_PATH.stat().st_mtime_ns
    except FileNotFoundError:
        mtime_ns = None

    if mtime_ns != _CONFIG_MTIME_NS:
        _FILE_CONFIG = _load_config()
        _CONFIG_MTIME_NS = mtime_ns
        CONFIG_VERSION += 1


def refresh_config() -> None:
    """Reload JSON-backed settings when .env.json changes on disk."""
    global OLLAMA_BASE_URLS, GEMINI_BASE_URL, AGENTROUTER_BASE_URL
    global DEFAULT_LOCAL_FALLBACK_MODEL

    _refresh_file_config()
    OLLAMA_BASE_URLS = _provider_urls(
        "OLLAMA", constants.DEFAULT_OLLAMA_BASE_URL
    )
    GEMINI_BASE_URL = os.getenv(
        "GEMINI_BASE_URL",
        _provider_value("GEMINI", "base_url", constants.DEFAULT_GEMINI_BASE_URL),
    )
    AGENTROUTER_BASE_URL = os.getenv(
        "AGENTROUTER_BASE_URL",
        _provider_value(
            "AGENTROUTER", "base_url", constants.DEFAULT_AGENTROUTER_BASE_URL
        ),
    )
    DEFAULT_LOCAL_FALLBACK_MODEL = _get_config_value(
        "DEFAULT_LOCAL_FALLBACK_MODEL", constants.DEFAULT_LOCAL_FALLBACK_MODEL
    )


HOST = constants.HOST
PORT = constants.PORT
GEMINI_API_VERSION = constants.GEMINI_API_VERSION
GEMINI_MODELS = list(constants.GEMINI_MODELS)
AGENTROUTER_MODELS = list(constants.AGENTROUTER_MODELS)
refresh_config()

def get_key_pool(env_var_name: str) -> list:
    """Return configured credentials, preferring process environment values."""
    _refresh_file_config()
    provider = {
        "GEMINI_API_KEYS": "GEMINI",
        "AGENTROUTER_API_KEYS": "AGENTROUTER",
    }.get(env_var_name)
    default = _provider_value(provider, "API_KEYS", []) if provider else []
    value = os.getenv(env_var_name, _FILE_CONFIG.get(env_var_name, default))
    if isinstance(value, list):
        return [str(key).strip() for key in value if str(key).strip()]
    return [key.strip() for key in str(value).split(",") if key.strip()]

def get_shuffled_keys(provider: str) -> list:
    """Returns a newly randomized copy of target account keys."""
    pool = get_key_pool("GEMINI_API_KEYS") if provider == "gemini" else get_key_pool("AGENTROUTER_API_KEYS")
    random.shuffle(pool)
    return pool


def get_configured_secrets() -> list[str]:
    """Return credential values that must never appear in application logs."""
    _refresh_file_config()
    secrets = []
    for provider in ("GEMINI", "AGENTROUTER"):
        settings = _FILE_CONFIG.get(provider, {})
        if not isinstance(settings, dict):
            continue
        keys = settings.get("API_KEYS", [])
        secrets.extend(keys if isinstance(keys, list) else [keys])
        params = settings.get("params", {})
        if isinstance(params, dict) and params.get("key"):
            secrets.append(params["key"])
    secrets.extend(get_key_pool("GEMINI_API_KEYS"))
    secrets.extend(get_key_pool("AGENTROUTER_API_KEYS"))
    return [str(secret) for secret in secrets if secret and "${" not in str(secret)]