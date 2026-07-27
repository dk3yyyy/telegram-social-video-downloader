# Contributing

Contributions that improve reliability, security, platform compatibility, tests, or documentation are welcome.

1. Fork the repository and create a focused branch.
2. Use synthetic Telegram payloads and public, non-sensitive test URLs.
3. Never commit bot tokens, API keys, cookies, credential IDs, webhook paths, chat IDs, real execution data, or downloaded media.
4. Install development dependencies and run `pytest`.
5. Build the container with `docker compose build` when changing runtime dependencies.
6. Explain user-visible behavior and failure-mode changes in the pull request.

Please keep the single-instance SQLite architecture unless a change fully implements and tests distributed job leases, retries, and idempotency.
