# Architecture and failure behavior

## Components

1. **Telegram Bot API** sends webhook updates to n8n and receives outbound messages/media.
2. **n8n** validates the update shape, classifies the message, and submits authenticated JSON requests.
3. **FastAPI service** authenticates requests, validates URLs, persists jobs, and exposes status.
4. **SQLite** stores job identity and state for restart recovery and idempotency.
5. **Worker threads** invoke yt-dlp and ffmpeg without a shell, then upload the result to Telegram.

## Data flow

The workflow extracts only `chat_id`, message text, first name, URL, and Telegram `update_id`. The downloader receives `chat_id`, the selected URL, and `request_id`. It does not receive the full Telegram update or a bot token.

Downloaded media exists only inside a per-job temporary directory and is deleted after delivery or failure. SQLite retains the source URL, chat ID, status, timestamps, and a bounded public error message. If this metadata is sensitive in your environment, apply filesystem encryption and a retention/cleanup policy.

## Trust boundaries

- The public webhook is untrusted input.
- The n8n-to-downloader boundary is authenticated with `X-API-Key`.
- Social-media URLs are untrusted even after hostname validation; yt-dlp remains a high-risk parser and must be patched.
- Telegram is an external destination. The bot token never leaves the downloader process.

## Failure behavior

| Failure | Behavior |
|---|---|
| Missing or invalid API key | HTTP 401; no job created |
| Unsupported/unsafe URL | HTTP 422; no job created |
| Queue at capacity | HTTP 503; job marked failed |
| Duplicate `request_id` | Existing job returned; no duplicate download |
| Process restart | `running` jobs reset to `queued` and are retried |
| yt-dlp/ffmpeg failure | Job marked failed with a bounded, non-sensitive error |
| Telegram rejection/network error | Job marked failed; no automatic retry in v1 |
| Media above configured limit after transcode | Job marked failed |

## Scaling boundary

Run one application instance. Multiple replicas would each own an in-memory queue while sharing SQLite, which is not a safe distributed-worker design. For horizontal scaling, replace the queue and store with Redis/PostgreSQL plus explicit leases and retry policies.
