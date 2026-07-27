# Downloader API

All endpoints except `/healthz` require:

```http
X-API-Key: <DOWNLOADER_API_KEY>
```

## `GET /healthz`

Returns `200` when the HTTP process is alive. It does not test Telegram or social-platform connectivity.

## `POST /send_async`

Queues a supported social-video URL.

```json
{
  "chat_id": "123456789",
  "url": "https://x.com/example/status/123",
  "request_id": "987654321"
}
```

Response (`202`):

```json
{
  "job_id": "00000000-0000-0000-0000-000000000000",
  "status": "queued",
  "duplicate": false
}
```

`request_id` is optional but strongly recommended. The workflow supplies Telegram's `update_id` so webhook retries do not duplicate downloads.

## `GET /status/{job_id}`

Returns `queued`, `running`, `succeeded`, or `failed`. Failure messages are intentionally generic and bounded.

## `POST /send_message`

Sends a plain Telegram message through the server-side bot client.

```json
{
  "chat_id": "123456789",
  "text": "Hello"
}
```

This design keeps the bot token out of n8n workflow URLs and request payloads.
