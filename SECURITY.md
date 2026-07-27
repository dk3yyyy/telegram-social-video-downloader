# Security policy

## Supported versions

Security fixes are applied to the latest commit on `main`. No older release line is currently maintained.

## Report a vulnerability

Use GitHub's **Report a vulnerability** form in the repository Security tab. Do not open a public issue for exploitable behavior, leaked credentials, webhook paths, private URLs, chat IDs, or personal data.

Include a minimal reproduction, affected component, expected impact, and suggested mitigation if known. Use synthetic data only.

## Secret exposure

If a real token or API key is exposed, rotate or revoke it immediately at its issuer. Removing it from the latest commit does not remove it from Git history, forks, caches, or logs.

## Scope

Security reports about the repository's code and default configuration are welcome. Vulnerabilities in Telegram, n8n, yt-dlp, ffmpeg, or individual social platforms should also be reported to the relevant upstream project.
