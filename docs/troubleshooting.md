# Troubleshooting

## n8n cannot resolve `downloader`

Both containers must share the external Docker network named by `AUTOMATION_NETWORK` (default: `automation`). Run `docker network inspect automation` and confirm both the n8n and downloader containers are listed. Prefer declaring the external network in both Compose files rather than relying on a one-off `docker network connect` command.

## n8n says environment-variable access is blocked

Your n8n deployment may disable `$env` expressions. Configure a non-secret base URL directly and use an n8n Header Auth credential for `X-API-Key`. Do not place secrets in query parameters or exported workflow JSON.

## Telegram webhook receives no updates

- Confirm the n8n workflow is active.
- Confirm the registered URL is the production webhook, not the temporary test URL.
- Inspect Telegram `getWebhookInfo` for the last error.
- Verify the public certificate and reverse-proxy route.
- Ensure only one intended webhook is registered for the bot.

## The downloader returns 401

`DOWNLOADER_API_KEY` differs between n8n and the downloader. Update both runtimes and restart them. Do not print the actual key while diagnosing.

## A URL returns 422

Only TikTok, Instagram, X/Twitter, Facebook, and `fb.watch` hosts are accepted. URLs with credentials, custom ports, unsupported schemes, or lookalike domains are rejected.

## A job fails after being queued

Query `/status/{job_id}` with the API key. Common causes include platform extraction changes, login/DRM restrictions, timeouts, unavailable media, Telegram rejection, and output remaining above the configured size limit.

Check container logs, but do not share them publicly until URLs, chat IDs, and infrastructure details are redacted.

## yt-dlp extraction suddenly stops working

Build a fresh image to pull a supported yt-dlp release:

```bash
docker compose build --pull --no-cache downloader
docker compose up -d downloader
```

Run tests and try a public, non-sensitive sample before restoring production traffic.

## Video is sent as a document

Files at or below `document_threshold_bytes` are intentionally sent as documents. Larger files use `sendVideo` with probed width, height, and duration. Change the threshold only after testing Telegram behavior for portrait and landscape media.
