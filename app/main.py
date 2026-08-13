import json
import logging
import random
from contextlib import asynccontextmanager
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from helpers import backends, config, formatters

logger = logging.getLogger("AgentRouter.Server")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.refresh_config()
    logger.info("Starting model discovery and health checks")
    await backends.initialize_model_health()
    logger.info("Model discovery and health checks complete")
    yield


app = FastAPI(
    title="Modular Unified Multi-Format Agent Router", lifespan=lifespan
)


async def stream_orchestrator(
    target_url: str,
    keys_pool: list,
    payload: dict,
    is_anthropic: bool,
    model_name: str,
    is_ollama: bool,
):
    """Coordinate data chunk delivery and local fallback handling."""
    msg_id = f"msg_{random.randint(1000, 9999)}"

    if is_anthropic:
        yield formatters.anthropic_stream_start(msg_id, model_name)

    import httpx

    is_gemini = "/models/" in target_url and ":generateContent" in target_url
    stream_url = target_url
    request_payload = payload
    headers = {"Content-Type": "application/json"}
    if is_gemini:
        stream_url = target_url.replace(":generateContent", ":streamGenerateContent")
        stream_url = f"{stream_url}?{urlencode({'alt': 'sse'})}"
        request_payload = formatters.openai_to_gemini_json(payload)
        if keys_pool and keys_pool[0]:
            headers["x-goog-api-key"] = keys_pool[0]
    elif keys_pool and keys_pool[0] and not is_ollama:
        if target_url.startswith(f"{config.AGENTROUTER_BASE_URL}/"):
            headers.update(
                config.get_provider_settings("AGENTROUTER").get("headers", {})
            )
        headers["Authorization"] = f"Bearer {keys_pool[0]}"

    async with httpx.AsyncClient() as client, client.stream(
            "POST", stream_url, json=request_payload, headers=headers, timeout=60.0
    ) as response:
            if response.is_error:
                logger.warning(
                    "Streaming request failed for %s with HTTP %s",
                    model_name,
                    response.status_code,
                )
                error = {
                    "type": "error",
                    "error": {"type": "upstream_error", "message": "Model streaming request failed"},
                }
                if is_anthropic:
                    yield f"event: error\ndata: {json.dumps(error)}\n\n"
                else:
                    yield f"data: {json.dumps(error)}\n\n"
                return
            async for line in response.aiter_lines():
                if not line:
                    continue
                data_str = line[6:].strip() if line.startswith("data: ") else line.strip()
                if data_str == "[DONE]":
                    if not is_anthropic:
                        yield "data: [DONE]\n\n"
                    break
                try:
                    chunk_json = json.loads(data_str)
                    if is_gemini:
                        candidates = chunk_json.get("candidates", [])
                        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                        delta_text = "".join(part.get("text", "") for part in parts)
                    else:
                        delta_text = chunk_json.get("choices", [{}])[0].get(
                            "delta", {}
                        ).get("content", "")
                    if delta_text:
                        if is_anthropic:
                            yield formatters.to_anthropic_stream_chunk(
                                delta_text, msg_id
                            )
                        else:
                            yield f"data: {json.dumps(chunk_json)}\n\n"
                except (TypeError, ValueError, IndexError):
                    continue

    if is_anthropic:
        yield formatters.anthropic_stream_end()


async def master_pipeline(body: dict, is_anthropic_client: bool):
    """Process, route, and normalize requests."""
    config.refresh_config()
    model_name = body.get("model")
    should_stream = body.get("stream", False)
    if not model_name:
        raise HTTPException(status_code=400, detail="Missing model name framework parameter.")
    is_unavailable = model_name.startswith(config.constants.UNAVAILABLE_MODEL_PREFIX)
    routed_model = model_name.removeprefix(config.constants.UNAVAILABLE_MODEL_PREFIX)
    routed_model = routed_model.removeprefix(config.constants.MODEL_ALIAS_PREFIX)
    if is_unavailable:
        raise HTTPException(
            status_code=503,
            detail=f"Model '{routed_model}' is currently unavailable.",
        )
    model_name = routed_model

    messages = (
        formatters.anthropic_to_openai_messages(body)
        if is_anthropic_client
        else body.get("messages", [])
    )
    openai_payload = {"model": model_name, "messages": messages, "stream": should_stream}

    ollama_list = await backends.get_ollama_models()
    gemini_list = await backends.get_gemini_models()
    agentrouter_list = await backends.get_agentrouter_models()
    target_url, keys_pool, is_ollama = backends.resolve_route_details(
        model_name, ollama_list, gemini_list, agentrouter_list
    )
    if not target_url:
        raise HTTPException(
            status_code=404,
            detail=f"Model path '{model_name}' unrecognized by mapping files.",
        )

    if should_stream:
        return StreamingResponse(
            stream_orchestrator(
                target_url,
                keys_pool,
                openai_payload,
                is_anthropic_client,
                model_name,
                is_ollama,
            ),
            media_type="text/event-stream",
        )

    backend_json, final_model = await backends.fetch_json_with_retry(
        target_url, keys_pool, openai_payload, is_ollama
    )
    if is_anthropic_client:
        return JSONResponse(
            content=formatters.openai_to_anthropic_json(backend_json, final_model)
        )
    return JSONResponse(content=backend_json)


@app.get("/v1/models")
async def list_models():
    config.refresh_config()
    models = await backends.get_model_inventory()
    return {
        "object": "list",
        "data": [
            {
                "id": model,
                "object": "model",
                "created": 0,
                "owned_by": "claude-router",
            }
            for model in models
        ],
    }


@app.post("/v1/messages")
async def anthropic_endpoint(request: Request):
    return await master_pipeline(await request.json(), is_anthropic_client=True)


@app.post("/v1/chat/completions")
async def openai_endpoint(request: Request):
    return await master_pipeline(await request.json(), is_anthropic_client=False)
