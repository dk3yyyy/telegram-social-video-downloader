# Security notes

## Secrets

Never commit `.env`, exported n8n credentials, workflow execution data, Telegram updates from real users, cookies, webhook registration responses, or reverse-proxy logs containing secret paths.

Use separate values for:

- `TELEGRAM_BOT_TOKEN`: known only to the downloader service
- `DOWNLOADER_API_KEY`: shared only between n8n and the downloader
- `TELEGRAM_WEBHOOK_SECRET`: shared only between Telegram webhook registration and n8n
- Randomized n8n webhook path: treated as defense-in-depth, not primary authentication

Rotate the affected secret if it appears in a commit, issue, log, screenshot, or workflow URL. Deleting a Git commit is not sufficient after publication.

## Network exposure

The compose configuration binds to `127.0.0.1:8080` and uses a shared external Docker network for n8n. Prefer a private Docker network, VPN, or private service network. If public exposure is unavoidable, add TLS, rate limiting, request-size limits, and upstream access controls.

## Abuse and resource controls

The implementation provides bounded download size/duration, queue and worker counts, process-group timeout cleanup, and Compose CPU/memory/PID/tmpfs limits. Production operators should also enforce:

- Per-chat and per-IP rate limits at n8n or the reverse proxy
- CPU, memory, process, and disk quotas
- Temporary-volume size limits
- Job-history retention appropriate to your privacy requirements
- Monitoring for queue saturation and repeated failures

## URL handling

The SQLite volume contains Telegram chat IDs and submitted URLs. Restrict filesystem access and back it up only if operationally required. Completed and failed jobs are removed on service startup after `JOB_RETENTION_DAYS` (seven days by default); queued and running jobs are retained for recovery.

The allowlist blocks obvious SSRF targets and ambiguous URLs, but yt-dlp follows platform redirects internally. Keep yt-dlp patched and run this service in a restricted network segment without access to cloud metadata or internal administration services.

## Delivery semantics

Jobs use at-least-once processing. If the service exits after Telegram accepts an upload but before SQLite records success, startup recovery can deliver that media again. Telegram's Bot API does not provide an idempotency key for sends; operators should monitor restarts and accept this bounded duplicate risk.

## Reporting vulnerabilities

Do not open a public issue containing an exploit or secret. Use GitHub's private vulnerability reporting for this repository.
