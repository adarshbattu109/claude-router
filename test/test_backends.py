from helpers import backends, config


def test_resolve_ollama_route(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URLS", ["http://ollama.local"])

    target_url, keys, is_ollama = backends.resolve_route_details(
        "llama3", ["llama3"]
    )

    assert target_url == "http://ollama.local/v1/chat/completions"
    assert keys == [None]
    assert is_ollama is True


def test_resolve_cloud_route_uses_provider_keys(monkeypatch):
    monkeypatch.setattr(config, "get_shuffled_keys", lambda provider: ["key"])

    target_url, keys, is_ollama = backends.resolve_route_details(
        "meta-llama/llama-3-70b-instruct", []
    )

    assert target_url.endswith("/v1/chat/completions")
    assert keys == ["key"]
    assert is_ollama is False


def test_resolve_discovered_gemini_route(monkeypatch):
    monkeypatch.setattr(config, "get_shuffled_keys", lambda provider: ["key"])
    monkeypatch.setattr(config, "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")

    target_url, keys, is_ollama = backends.resolve_route_details(
        "gemini-2.5-flash", [], ["gemini-2.5-flash"]
    )

    assert target_url == (
        "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"
    )
    assert keys == ["key"]
    assert is_ollama is False


def test_unknown_model_has_no_route():
    assert backends.resolve_route_details("unknown-model", []) == (None, [], False)
