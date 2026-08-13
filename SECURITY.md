# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a Vulnerability

Please do not open a public issue for a security vulnerability. Use [GitHub Private Vulnerability Reporting](https://github.com/adarshbattu109/claude-router/security/advisories/new) when available, or email **adarsh.battu109@gmail.com**.

Include:

- A description of the vulnerability.
- Reproduction steps or a proof of concept.
- The potential impact.
- A suggested fix, if available.

Please allow up to 72 hours for acknowledgment. We will coordinate disclosure with the reporter and affected maintainers.

## Credential Handling

- Never commit `.env.json`, provider keys, or local configuration files.
- Rotate any key exposed in an issue, log, terminal transcript, or chat.
- The router forwards requests to configured third-party providers; review their retention and training policies before sending sensitive content.
- Keep the server bound to `127.0.0.1` unless network exposure is intentional and access controls are added.
- Do not treat the local `ANTHROPIC_AUTH_TOKEN` placeholder as authentication for a network-exposed deployment.
