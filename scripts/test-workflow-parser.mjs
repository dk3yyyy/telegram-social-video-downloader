import assert from 'node:assert/strict';
import fs from 'node:fs';

const workflow = JSON.parse(fs.readFileSync(new URL('../workflow/workflow.json', import.meta.url), 'utf8'));
const node = workflow.nodes.find((candidate) => candidate.name === 'Parse Telegram Update');
assert.ok(node, 'Parse Telegram Update node is missing');
const parse = new Function('$json', '$env', node.parameters.jsCode);
const webhookSecret = 'synthetic-webhook-secret-for-tests'; // pragma: allowlist secret

function run(text, updateId = 42) {
  const output = parse({
    headers: { 'x-telegram-bot-api-secret-token': webhookSecret },
    body: {
      update_id: updateId,
      message: { text, chat: { id: 123 }, from: { first_name: 'Example' } },
    },
  }, { TELEGRAM_WEBHOOK_SECRET: webhookSecret });
  return output[0].json;
}

assert.equal(run('/start').is_start, true);
assert.equal(run('https://x.com/user/status/123).').platform, 'X/Twitter');
assert.equal(run('https://vt.tiktok.com/abc').platform, 'TikTok');
assert.equal(run('https://fb.watch/abc').platform, 'Facebook');
assert.equal(run('instagram.com https://example.com/video').supported, false);
assert.equal(run('https://instagram.com.evil.example/video').supported, false);
assert.equal(run('https://user:password@x.com/video').supported, false); // pragma: allowlist secret
assert.equal(run('https://x.com:8443/video').supported, false);
assert.equal(run('https://www.instagram.com/reel/abc', 987).request_id, '987');
assert.throws(
  () => parse({ headers: {}, body: {} }, { TELEGRAM_WEBHOOK_SECRET: webhookSecret }),
  /Unauthorized Telegram webhook request/,
);
assert.throws(
  () => parse({ headers: { 'x-telegram-bot-api-secret-token': 'wrong' }, body: {} }, { TELEGRAM_WEBHOOK_SECRET: webhookSecret }),
  /Unauthorized Telegram webhook request/,
);

console.log('workflow_parser_tests=pass');
