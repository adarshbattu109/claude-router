import json

from helpers import config


def test_json_config_changes_are_reloaded(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTROUTER_BASE_URL", raising=False)
    config_path = tmp_path / ".env.json"
    config_path.write_text(
        json.dumps({"AGENTROUTER_BASE_URL": "https://first.example"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    config.refresh_config()
    assert config.AGENTROUTER_BASE_URL == "https://first.example"

    config_path.write_text(
        json.dumps({"AGENTROUTER_BASE_URL": "https://second.example"}),
        encoding="utf-8",
    )
    config.refresh_config()

    assert config.AGENTROUTER_BASE_URL == "https://second.example"


    def test_provider_config_uses_nested_base_url_and_keys(tmp_path, monkeypatch):
        monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
        monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
        config_path = tmp_path / ".env.json"
        config_path.write_text(
            json.dumps(
                {
                    "GEMINI": {
                        "base_url": "https://gemini.example",
                        "API_KEYS": ["key-one", "key-two"],
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(config, "CONFIG_PATH", config_path)
        config.refresh_config()

        assert config.GEMINI_BASE_URL == "https://gemini.example"
        assert config.get_key_pool("GEMINI_API_KEYS") == ["key-one", "key-two"]