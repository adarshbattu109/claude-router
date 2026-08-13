import logging

from claude_router import SecretRedactionFilter


def test_secret_redaction_filter_masks_configured_secret(monkeypatch):
    monkeypatch.setattr(
        "helpers.config.get_configured_secrets", lambda: ["secret-key"]
    )
    record = logging.LogRecord(
        "test", logging.ERROR, __file__, 1, "request key=%s", ("secret-key",), None
    )

    assert SecretRedactionFilter().filter(record) is True
    assert record.getMessage() == "request key=[REDACTED]"