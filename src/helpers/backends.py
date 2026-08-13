import asyncio
import logging
import random

import httpx

from helpers import config, formatters

logger = logging.getLogger("AgentRouter.Backends")

_HEALTH_CHECK_CONCURRENCY = 5
_HEALTHY_MODELS: set[str] = set()
_UNHEALTHY_MODELS: set[str] = set()
_MODEL_CATALOG: list[str] = []
_HEALTH_INITIALIZED = False
_HEALTH_REFRESH_TASK: asyncio.Task | None = None
_HEALTH_LOCK = asyncio.Lock()
_HEALTH_CONFIG_VERSION: int | None = None

async def get_ollama_models() -> list:
    """Query the first configured Ollama node for local models."""
    return await discover_models(
        "OLLAMA",
        timeout=1.0,
        parse_models=lambda data: [model["name"] for model in data["models"]],
    )

async def get_gemini_models() -> list:
    """Query Gemini for models supporting text generation."""
    return await discover_models(
        "GEMINI",
        timeout=5.0,
        parse_models=lambda data: [
            model["name"].removeprefix("models/")
            for model in data["models"]
            if "generateContent" in model.get("supportedGenerationMethods", [])
        ],
    )


async def get_agentrouter_models() -> list:
    """Query AgentRouter for its OpenAI-compatible model catalog."""
    return await discover_models(
        "AGENTROUTER",
        timeout=5.0,
        parse_models=lambda data: [
            model["id"]
            for model in data["data"]
            if isinstance(model, dict) and model.get("id")
        ],
    )


async def discover_models(
    provider: str,
    timeout: float,
    parse_models,
    params_factory=None,
) -> list:
    """Discover models using provider settings from .env.json."""
    settings = config.get_provider_settings(provider)
    base_url = settings.get("base_url", "").rstrip("/")
    discovery_path = settings.get("discovery_path", "")
    keys = settings.get("API_KEYS", []) or [None]
    configured_headers = settings.get("headers", {})
    auth_header = settings.get("auth_header")
    auth_scheme = settings.get("auth_scheme", "Bearer")
    if not keys:
        logger.info("Model discovery skipped for %s: no API keys configured", provider)
        return []
    async with httpx.AsyncClient() as client:
        for key in keys:
            try:
                headers = dict(configured_headers)
                if key and auth_header:
                    headers[auth_header] = f"{auth_scheme} {key}"
                params = settings.get("params")
                if params and key:
                    params = {
                        name: value.replace("${API_KEY}", key)
                        if isinstance(value, str)
                        else value
                        for name, value in params.items()
                    }
                    if "key" in params:
                        params["key"] = key
                response = await client.get(
                    f"{base_url}/{discovery_path.lstrip('/')}",
                    headers=headers or None,
                    params=params_factory(key) if params_factory else params,
                    timeout=timeout,
                )
                response.raise_for_status()
                models = parse_models(response.json())
                logger.info("Discovered %d models from %s", len(models), provider)
                return models
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
                logger.warning(
                    "Model discovery failed for %s (%s)", provider, type(error).__name__
                )
                continue
    logger.warning("No models discovered for %s", provider)
    return []

def resolve_route_details(
    model_name: str,
    ollama_list: list,
    gemini_list: list | None = None,
    agentrouter_list: list | None = None,
) -> tuple:
    """Identifies URL endpoints, active key sets, and routing metadata."""
    if model_name in ollama_list and config.OLLAMA_BASE_URLS:
        return f"{random.choice(config.OLLAMA_BASE_URLS)}/v1/chat/completions", [None], True
        
    available_gemini_models = gemini_list or config.GEMINI_MODELS
    if model_name in available_gemini_models:
        return (
            f"{config.GEMINI_BASE_URL}/{config.GEMINI_API_VERSION}/models/{model_name}:generateContent",
            config.get_shuffled_keys("gemini"),
            False,
        )
        
    available_agentrouter_models = agentrouter_list or config.AGENTROUTER_MODELS
    if model_name in available_agentrouter_models or "/" in model_name:
        return (
            f"{config.AGENTROUTER_BASE_URL}/v1/chat/completions",
            config.get_shuffled_keys("agentrouter"),
            False,
        )
        
    return None, [], False

async def check_model_health(
    model_name: str,
    ollama_list: list,
    gemini_list: list,
    agentrouter_list: list,
) -> bool:
    """Perform a bounded real request without allowing local fallback."""
    target_url, keys_pool, is_ollama = resolve_route_details(
        model_name, ollama_list, gemini_list, agentrouter_list
    )
    if not target_url:
        return False

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Reply with OK"}],
        "stream": False,
        "max_tokens": 4,
    }
    try:
        response, returned_model = await fetch_json_with_retry(
            target_url, keys_pool, payload, is_ollama, allow_fallback=False
        )
        content = response.get("choices", [{}])[0].get("message", {}).get(
            "content", ""
        ) if isinstance(response, dict) else ""
        return returned_model == model_name and bool(content.strip())
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return False


async def initialize_model_health() -> None:
    """Discover and concurrently health-check all configured model routes."""
    global _HEALTH_INITIALIZED, _MODEL_CATALOG, _HEALTH_CONFIG_VERSION
    async with _HEALTH_LOCK:
        if _HEALTH_INITIALIZED and _HEALTH_CONFIG_VERSION == config.CONFIG_VERSION:
            return
        _HEALTHY_MODELS.clear()
        _UNHEALTHY_MODELS.clear()
        ollama_list = await get_ollama_models()
        gemini_list = await get_gemini_models()
        agentrouter_list = await get_agentrouter_models()
        agentrouter_list = agentrouter_list or config.AGENTROUTER_MODELS
        _MODEL_CATALOG = list(
            dict.fromkeys(ollama_list + gemini_list + agentrouter_list)
        )
        semaphore = asyncio.Semaphore(_HEALTH_CHECK_CONCURRENCY)

        async def bounded_check(model_name: str) -> tuple[str, bool]:
            async with semaphore:
                return model_name, await check_model_health(
                    model_name, ollama_list, gemini_list, agentrouter_list
                )

        results = await asyncio.gather(
            *(bounded_check(model_name) for model_name in _MODEL_CATALOG)
        )
        _HEALTHY_MODELS.update(model for model, healthy in results if healthy)
        _UNHEALTHY_MODELS.update(model for model, healthy in results if not healthy)
        _HEALTH_INITIALIZED = True
        _HEALTH_CONFIG_VERSION = config.CONFIG_VERSION
        logger.info(
            "Model health initialized: %d healthy, %d unhealthy, %d total",
            len(_HEALTHY_MODELS),
            len(_UNHEALTHY_MODELS),
            len(_MODEL_CATALOG),
        )
        logger.info("Healthy models: %s", ", ".join(sorted(_HEALTHY_MODELS)) or "none")
        logger.info(
            "Unhealthy models: %s",
            ", ".join(sorted(_UNHEALTHY_MODELS)) or "none",
        )


async def get_healthy_models() -> list[str]:
    await initialize_model_health()
    return [model for model in _MODEL_CATALOG if model in _HEALTHY_MODELS]


async def get_model_inventory() -> list[str]:
    """Return all discovered models, marking unhealthy ones as unavailable."""
    await initialize_model_health()
    healthy_models = [
        f"{config.constants.MODEL_ALIAS_PREFIX}{model}"
        for model in _MODEL_CATALOG
        if model in _HEALTHY_MODELS
    ]
    unavailable_models = [
        f"{config.constants.UNAVAILABLE_MODEL_PREFIX}"
        f"{config.constants.MODEL_ALIAS_PREFIX}{model}"
        for model in _MODEL_CATALOG
        if model not in _HEALTHY_MODELS
    ]
    return healthy_models + unavailable_models


async def refresh_unhealthy_models() -> None:
    """Retry unhealthy models after a request triggers a fallback."""
    ollama_list = await get_ollama_models()
    gemini_list = await get_gemini_models()
    agentrouter_list = await get_agentrouter_models()
    agentrouter_list = agentrouter_list or config.AGENTROUTER_MODELS
    unhealthy = list(_UNHEALTHY_MODELS)
    results = await asyncio.gather(
        *(
            check_model_health(model, ollama_list, gemini_list, agentrouter_list)
            for model in unhealthy
        )
    )
    for model, healthy in zip(unhealthy, results):
        if healthy:
            _UNHEALTHY_MODELS.discard(model)
            _HEALTHY_MODELS.add(model)
    logger.info(
        "Unhealthy model refresh complete: %d recovered, %d still unhealthy",
        sum(results),
        len(_UNHEALTHY_MODELS),
    )
    logger.info("Healthy models: %s", ", ".join(sorted(_HEALTHY_MODELS)) or "none")
    logger.info(
        "Unhealthy models: %s",
        ", ".join(sorted(_UNHEALTHY_MODELS)) or "none",
    )


def schedule_unhealthy_refresh(model_name: str) -> None:
    """Mark a fallback model unhealthy and schedule one non-blocking refresh."""
    global _HEALTH_REFRESH_TASK
    _HEALTHY_MODELS.discard(model_name)
    _UNHEALTHY_MODELS.add(model_name)
    if _HEALTH_REFRESH_TASK is None or _HEALTH_REFRESH_TASK.done():
        _HEALTH_REFRESH_TASK = asyncio.create_task(refresh_unhealthy_models())


async def fetch_json_with_retry(
    target_url: str,
    keys_pool: list,
    payload: dict,
    is_ollama: bool,
    allow_fallback: bool = True,
) -> tuple:
    """Sends normal JSON payloads while rotating bad tokens or switching to local fallbacks."""
    async with httpx.AsyncClient() as client:
        available_keys = list(keys_pool)
        
        while available_keys:
            current_key = available_keys[0]
            headers = {"Content-Type": "application/json"}
            is_gemini = "/models/" in target_url and ":generateContent" in target_url
            is_agentrouter = target_url.startswith(
                f"{config.AGENTROUTER_BASE_URL}/"
            )
            request_payload = (
                formatters.openai_to_gemini_json(payload) if is_gemini else payload
            )
            if is_gemini:
                headers["x-goog-api-key"] = current_key
            elif current_key and not is_ollama:
                provider_headers = config.get_provider_settings(
                    "AGENTROUTER"
                ).get("headers", {}) if is_agentrouter else {}
                headers.update(provider_headers)
                headers["Authorization"] = f"Bearer {current_key}"

            try:
                res = await client.post(
                    target_url, json=request_payload, headers=headers, timeout=30.0
                )
                
                # Check for rate-limiting or token validation failures
                if res.status_code >= 400 and len(available_keys) > 1:
                    logger.warning(f"Key failed ({res.status_code}). Swapping to backup token...")
                    available_keys.pop(0)
                    continue
                elif res.status_code >= 400 and len(available_keys) == 1 and not is_ollama:
                    break # All cloud keys exhausted. Trigger fallback.
                
                response_json = res.json()
                if is_gemini:
                    response_json = formatters.gemini_to_openai_json(
                        response_json, payload["model"]
                    )
                return response_json, payload["model"]
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                if len(available_keys) > 1:
                    available_keys.pop(0)
                    continue
                break

        # --- LOCAL OFFLINE FALLBACK ---
        if not is_ollama and allow_fallback:
            logger.error("Cloud down or keys exhausted. Executing offline local fallback...")
            schedule_unhealthy_refresh(payload["model"])
            local_models = await get_ollama_models()
            fallback_model = config.DEFAULT_LOCAL_FALLBACK_MODEL
            if fallback_model not in local_models:
                if not local_models:
                    raise httpx.ConnectError("No local Ollama models are available for fallback.")
                fallback_model = local_models[0]
                logger.warning(
                    "Configured fallback model %s is unavailable; using %s",
                    config.DEFAULT_LOCAL_FALLBACK_MODEL,
                    fallback_model,
                )
            fallback_url = f"{random.choice(config.OLLAMA_BASE_URLS)}/v1/chat/completions"
            payload["model"] = fallback_model
            res = await client.post(fallback_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30.0)
            return res.json(), fallback_model

        raise httpx.ConnectError("All network connections and local hardware hooks failed.")