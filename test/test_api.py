from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_models_endpoint_includes_configured_cloud_models(monkeypatch):
    async def healthy_models():
        return [
            "claude-router/gemini-3.5-flash",
            "unavailable/claude-router/gemini-2.5-flash",
            "claude-router/meta-llama/llama-3-70b-instruct",
        ]

    monkeypatch.setattr("app.main.backends.get_model_inventory", healthy_models)

    response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["object"] == "list"
    assert response.json()["data"][0]["owned_by"] == "claude-router"
    model_ids = {model["id"] for model in response.json()["data"]}
    assert "claude-router/gemini-3.5-flash" in model_ids
    assert "unavailable/claude-router/gemini-2.5-flash" in model_ids
    assert "claude-router/meta-llama/llama-3-70b-instruct" in model_ids


def test_unavailable_model_returns_service_unavailable():
    response = client.post(
        "/v1/messages",
        json={
            "model": "unavailable/claude-router/gemini-2.5-flash",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 503
    assert "gemini-2.5-flash" in response.json()["detail"]


def test_messages_requires_model():
    response = client.post("/v1/messages", json={"messages": []})

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing model name framework parameter."


def test_chat_completions_requires_model():
    response = client.post("/v1/chat/completions", json={"messages": []})

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing model name framework parameter."
