import json

from helpers import formatters


def test_anthropic_messages_convert_to_openai_messages():
    body = {
        "system": "Be concise.",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "image", "source": "ignored"},
                    {"type": "text", "text": "world"},
                ],
            }
        ],
    }

    assert formatters.anthropic_to_openai_messages(body) == [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Hello world"},
    ]


def test_openai_json_converts_to_anthropic_message():
    response = formatters.openai_to_anthropic_json(
        {"choices": [{"message": {"content": "Hello"}}]}, "llama3"
    )

    assert response["type"] == "message"
    assert response["role"] == "assistant"
    assert response["model"] == "llama3"
    assert response["content"] == [{"type": "text", "text": "Hello"}]


def test_openai_payload_converts_to_gemini_request():
    request = formatters.openai_to_gemini_json(
        {
            "messages": [
                {"role": "system", "content": "Be brief."},
                {"role": "user", "content": "Hi"},
            ],
            "max_tokens": 16,
        }
    )

    assert request == {
        "systemInstruction": {"parts": [{"text": "Be brief."}]},
        "contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
        "generationConfig": {"maxOutputTokens": 16},
    }


def test_gemini_response_converts_to_openai_response():
    response = formatters.gemini_to_openai_json(
        {
            "responseId": "response-1",
            "candidates": [{"content": {"parts": [{"text": "Hello"}]}}],
        },
        "gemini-2.5-flash",
    )

    assert response["choices"][0]["message"]["content"] == "Hello"


def test_anthropic_stream_chunk_is_sse():
    chunk = formatters.to_anthropic_stream_chunk("Hi", "msg_1")

    assert chunk.startswith("event: content_block_delta\n")
    assert json.loads(chunk.split("data: ", 1)[1])["delta"]["text"] == "Hi"


def test_anthropic_stream_has_complete_event_lifecycle():
    start = formatters.anthropic_stream_start("msg_1", "llama3.2:3b")
    end = formatters.anthropic_stream_end()

    assert "event: message_start" in start
    assert "event: content_block_start" in start
    assert "event: content_block_stop" in end
    assert "event: message_delta" in end
    assert "event: message_stop" in end
