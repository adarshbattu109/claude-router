import asyncio

from helpers import backends, config


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "data": [
                {"id": "claude-opus-4-8", "object": "model"},
                {"id": "gpt-5.6-sol", "object": "model"},
            ]
        }


class FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, headers, params, timeout):
        assert url == f"{config.AGENTROUTER_BASE_URL}/v1/models"
        assert headers["Authorization"] == "Bearer agentrouter-key"
        assert headers["Accept"] == "application/json"
        assert params is None
        assert timeout == 5.0
        return FakeResponse()


def test_get_agentrouter_models_uses_json_discovery(monkeypatch):
    monkeypatch.setattr(
        config, "get_shuffled_keys", lambda provider: ["agentrouter-key"]
    )
    monkeypatch.setattr("helpers.backends.httpx.AsyncClient", FakeClient)

    assert asyncio.run(backends.get_agentrouter_models()) == [
        "claude-opus-4-8",
        "gpt-5.6-sol",
    ]