import json
import random


def anthropic_to_openai_messages(body: dict) -> list:
    """Extracts structural system text and message tracks into OpenAI formatting arrays."""
    openai_messages = []
    if body.get("system"):
        openai_messages.append({"role": "system", "content": body["system"]})
        
    for msg in body.get("messages", []):
        content = msg.get("content")
        if isinstance(content, list):
            content = " ".join([item.get("text", "") for item in content if item.get("type") == "text"])
        openai_messages.append({"role": msg.get("role"), "content": content})
        
    return openai_messages


def openai_to_gemini_json(payload: dict) -> dict:
    """Convert the internal OpenAI-shaped request to Gemini generateContent."""
    contents = []
    system_instruction = None
    for message in payload.get("messages", []):
        role = message.get("role")
        content = message.get("content", "")
        parts = [{"text": content}] if isinstance(content, str) else content
        if role == "system":
            system_instruction = {"parts": parts}
            continue
        contents.append({"role": "model" if role == "assistant" else "user", "parts": parts})

    request = {"contents": contents}
    if system_instruction:
        request["systemInstruction"] = system_instruction
    generation_config = {}
    if payload.get("max_tokens") is not None:
        generation_config["maxOutputTokens"] = payload["max_tokens"]
    if payload.get("temperature") is not None:
        generation_config["temperature"] = payload["temperature"]
    if generation_config:
        request["generationConfig"] = generation_config
    return request


def gemini_to_openai_json(response: dict, model_name: str) -> dict:
    """Convert a Gemini generateContent response to the internal response shape."""
    text = ""
    candidates = response.get("candidates", []) if isinstance(response, dict) else []
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
    return {
        "id": response.get("responseId", "") if isinstance(response, dict) else "",
        "model": model_name,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
        "usage": response.get("usageMetadata", {}) if isinstance(response, dict) else {},
    }

def openai_to_anthropic_json(openai_json: dict, model_name: str) -> dict:
    """Wraps static JSON response models into Anthropic message schemas."""
    choices = openai_json.get("choices", []) if openai_json else []
    text_content = choices[0].get("message", {}).get("content", "") if choices else ""
    
    return {
        "id": f"msg_local_{random.randint(100,999)}",
        "type": "message",
        "role": "assistant",
        "model": model_name,
        "content": [{"type": "text", "text": text_content}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 0, "output_tokens": 0}
    }

def to_anthropic_stream_chunk(text: str, msg_id: str) -> str:
    """Formats raw textual content changes into clean Anthropic SSE data lines."""
    data = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": text}
    }
    return f"event: content_block_delta\ndata: {json.dumps(data)}\n\n"


def anthropic_stream_start(msg_id: str, model_name: str) -> str:
    message = {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "model": model_name,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }
    block = {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }
    return (
        f"event: message_start\ndata: {json.dumps(message)}\n\n"
        f"event: content_block_start\ndata: {json.dumps(block)}\n\n"
    )


def anthropic_stream_end() -> str:
    block = {"type": "content_block_stop", "index": 0}
    delta = {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 0},
    }
    stop = {"type": "message_stop"}
    return (
        f"event: content_block_stop\ndata: {json.dumps(block)}\n\n"
        f"event: message_delta\ndata: {json.dumps(delta)}\n\n"
        f"event: message_stop\ndata: {json.dumps(stop)}\n\n"
    )