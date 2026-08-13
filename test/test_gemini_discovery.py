import asyncio

from helpers import backends, config


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "models": [
                {
                    "name": "models/gemini-2.5-flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/text-embedding-004",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }


class FakeClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params, headers, timeout):
        assert url == f"{config.GEMINI_BASE_URL}/v1/models"
        assert params == {"key": "gemini-key"}
        assert headers is None
        assert timeout == 5.0
        return FakeResponse()


def test_get_gemini_models_filters_supported_models(monkeypatch):
    monkeypatch.setattr(
        config,
        "get_provider_settings",
        lambda provider: {
            "base_url": config.GEMINI_BASE_URL,
            "discovery_path": "/v1/models",
            "params": {"key": "${API_KEY}"},
            "API_KEYS": ["gemini-key"],
        },
    )
    monkeypatch.setattr("helpers.backends.httpx.AsyncClient", FakeClient)

    assert asyncio.run(backends.get_gemini_models()) == ["gemini-2.5-flash"]