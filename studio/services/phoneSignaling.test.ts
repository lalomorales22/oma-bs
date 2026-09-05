import { createServer } from 'node:http';
import { randomUUID } from 'node:crypto';
import { once } from 'node:events';
import WebSocket, { WebSocketServer } from 'ws';
import { expect, it } from 'vitest';
import { attachPhoneSignaling, pairingRequest } from '../phone-signaling.mjs';

it('requires explicit HTTPS LAN mode, matching Origin, and a full pairing token', () => {
  const req = {headers:{origin:'https://192.168.1.5:3000',host:'192.168.1.5:3000'},
    socket:{encrypted:true, remoteAddress:'192.168.1.9'}, url:`/phone-signal?session=${randomUUID()}&role=phone`};
  expect(pairingRequest(req)).toBeNull();
  expect(pairingRequest(req, true)?.role).toBe('phone');
  expect(pairingRequest({...req, headers:{...req.headers, origin:'https://evil.example'}}, true)).toBeNull();
  expect(pairingRequest({...req, url:'/phone-signal?session=12345678&role=phone'}, true)).toBeNull();
});

it('pairs two peers, rejects a third, and survives an oversized frame', async () => {
  const server = createServer(), clients: WebSocket[] = [];
  const closeSignaling = attachPhoneSignaling(server, WebSocketServer);
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const port = (server.address() as {port:number}).port, session = randomUUID();
  const connect = (role: string, origin = `http://127.0.0.1:${port}`, token = session) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/phone-signal?session=${token}&role=${role}`, {origin});
    ws.on('error', () => {}); clients.push(ws); return ws;
  };
  try {
    const absent = connect('phone'); await expect(once(absent, 'open')).rejects.toThrow('403');
    const desktop = connect('desktop'); await once(desktop, 'open');
    const phone = connect('phone'); await once(phone, 'open');
    const message = once(desktop, 'message'); phone.send(JSON.stringify({type:'offer',sdp:'test'}));
    expect(JSON.parse(String((await message)[0]))).toEqual({type:'offer',sdp:'test'});
    await expect(once(connect('phone'), 'open')).rejects.toThrow('403');
    await expect(once(connect('desktop', 'http://evil.example', randomUUID()), 'open')).rejects.toThrow('403');
    const closed = once(phone, 'close'); phone.send('x'.repeat(65537));
    expect((await closed)[0]).toBe(1009);
    const fresh = connect('desktop', undefined, randomUUID()); await once(fresh, 'open');
    expect(fresh.readyState).toBe(WebSocket.OPEN);
  } finally {
    clients.forEach(ws => ws.terminate()); closeSignaling();
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
});
