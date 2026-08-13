import logging
import sys
from pathlib import Path


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        from helpers import config

        message = record.getMessage()
        for secret in config.get_configured_secrets():
            message = message.replace(secret, "[REDACTED]")
        record.msg = message
        record.args = ()
        return True


def main() -> None:
    import uvicorn

    from helpers import config

    logging.basicConfig(level=logging.INFO)
    redaction_filter = SecretRedactionFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redaction_filter)

    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT)
