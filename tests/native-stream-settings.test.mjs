import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, chmod, rm, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { nativeStreamSettings } from '../studio/native-stream-settings.mjs';

async function call(path, changes = {}) {
  const req = { method: 'GET', socket: { remoteAddress: '127.0.0.1' },
    headers: { host: '127.0.0.1:4173', 'x-oma-bs-request': 'studio', 'sec-fetch-site': 'same-origin' }, ...changes };
  const res = { headers: {}, setHeader(k, v) { this.headers[k] = v; }, end(body) { this.body = JSON.parse(body); } };
  await nativeStreamSettings(path)(req, res);
  return res;
}

test('only the explicit local studio request can read the saved profile', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'oma-bs-stream-'));
  try {
    const path = join(dir, 'streaming.json');
    await writeFile(path, JSON.stringify({ version: 1, destinations: [{ key: 'test-secret' }] }), { mode: 0o600 });
    const allowed = await call(path);
    assert.equal(allowed.statusCode, 200);
    assert.equal(allowed.body.destinations[0].key, 'test-secret');
    assert.equal(allowed.headers['Cache-Control'], 'no-store');
    for (const changes of [
      { method: 'POST' }, { method: 'OPTIONS' },
      { socket: { remoteAddress: '192.168.1.20' } },
      { headers: { host: 'evil.example', 'x-oma-bs-request': 'studio' } },
      { headers: { host: '127.0.0.1:4173' } },
      { headers: { host: '127.0.0.1:4173', 'x-oma-bs-request': 'studio', origin: 'https://evil.example' } },
      { headers: { host: '127.0.0.1:4173', 'x-oma-bs-request': 'studio', 'sec-fetch-site': 'cross-site' } },
    ]) {
      const denied = await call(path, changes);
      assert.equal(denied.statusCode, 403);
      assert.ok(!JSON.stringify(denied.body).includes('test-secret'));
    }
    assert.equal((await call(undefined)).statusCode, 404);
    await chmod(path, 0o644);
    assert.equal((await call(path)).statusCode, 404);
    await chmod(path, 0o600);
    const link = join(dir, 'linked.json');
    await symlink(path, link);
    assert.equal((await call(link)).statusCode, 404);
  } finally { await rm(dir, { recursive: true, force: true }); }
});
