import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'node:net';
import { setTimeout as delay } from 'node:timers/promises';
import { createRelay, destinationSpec, localRequest } from '../studio/secure-relay.mjs';

test('relay rejects remote clients, foreign origins, and DNS rebinding', () => {
  const req = (host, origin, remoteAddress = '127.0.0.1') => ({headers:{host,origin},socket:{remoteAddress}});
  assert.equal(localRequest(req('127.0.0.1:4000', 'http://127.0.0.1:4173')), true);
  assert.equal(localRequest(req('localhost:4000', undefined)), true);
  assert.equal(localRequest(req('127.0.0.1:4000', 'https://evil.example')), false);
  assert.equal(localRequest(req('evil.example:4000', undefined)), false);
  assert.equal(localRequest(req('127.0.0.1:4000', undefined, '192.168.1.2')), false);
  assert.equal(localRequest(req('localhost:4000', 'null')), false);
});

test('credentials stay in preset content; malformed destinations are rejected', () => {
  const spec = destinationSpec({url:'rtmps://example.test/private-app?token=private-token',key:'private-key'});
  assert.equal(spec.endpoint, 'rtmps://example.test');
  assert.equal(spec.tls, true);
  assert.match(spec.preset, /rtmp_playpath=private-key/);
  for (const url of ['https://example.test/live', 'rtmp://user:pass@example.test/live', 'rtmp://example.test/live#secret']) {
    assert.throws(() => destinationSpec({url,key:'key'}));
  }
  assert.throws(() => destinationSpec({url:'rtmp://example.test/live',key:'key\nrtmp_app=other'}));
  assert.throws(() => createRelay([], () => {}));
});

async function freePort() {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

test('browser WebM reaches RTMP with audio despite another destination failing', {
  skip: spawnSync('ffmpeg', ['-version'], {stdio:'ignore'}).status !== 0, timeout:30000,
}, async () => {
  const folder = mkdtempSync(join(tmpdir(), 'oma-bs-browser-test-'));
  const children = [];
  let relay;
  const child = (args, stdio) => {
    const proc = spawn('ffmpeg', args, {stdio}); children.push(proc); return proc;
  };
  try {
    const port = await freePort(), badPort = await freePort();
    const output = join(folder, 'received.flv');
    const receiver = child(['-nostdin','-v','error','-listen','1','-i',`rtmp://127.0.0.1:${port}/app/test-key`,
      '-c','copy','-f','flv',output], ['ignore','ignore','ignore']);
    await delay(300);
    const messages = [];
    relay = createRelay([port,badPort].map(p => ({url:`rtmp://127.0.0.1:${p}/app`,key:'test-key'})), m => messages.push(m));
    const source = child(['-nostdin','-v','error','-re','-f','lavfi','-i','testsrc2=size=160x90:rate=30',
      '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-c:v','libvpx','-threads','1','-deadline','realtime',
      '-g','30','-c:a','libopus','-f','webm','-cluster_time_limit','500','pipe:1'], ['ignore','pipe','ignore']);
    source.stdout.on('data', chunk => relay.write(chunk));
    const deadline = Date.now() + 20000;
    while (!messages.some(m => m.state === 'partial' && m.sending === 1) && Date.now() < deadline) await delay(100);
    assert.ok(messages.some(m => m.state === 'partial' && m.sending === 1), JSON.stringify(messages));
    assert.ok(!messages.some(m => m.state === 'confirmed'), 'A failed destination must not be confirmed');
    source.kill('SIGTERM'); relay.close(); relay.close();
    for (let n = 0; n < 30 && receiver.exitCode === null; n++) await delay(100);
    const probe = spawnSync('ffprobe', ['-v','error','-show_streams','-of','json',output], {encoding:'utf8'});
    assert.equal(probe.status, 0, probe.stderr);
    const streams = JSON.parse(probe.stdout).streams;
    assert.ok(streams.some(s => s.codec_name === 'h264'));
    assert.ok(streams.some(s => s.codec_name === 'aac'));
  } finally {
    relay?.close();
    for (const proc of children) if (proc.exitCode === null && proc.signalCode === null) proc.kill('SIGTERM');
    await Promise.all(children.map(proc => proc.exitCode !== null || proc.signalCode !== null ? null : new Promise(resolve => {
      const timer = setTimeout(() => proc.kill('SIGKILL'), 1000);
      proc.once('close', () => { clearTimeout(timer); resolve(); });
    })));
    rmSync(folder, {recursive:true,force:true});
  }
});
