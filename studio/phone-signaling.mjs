export function pairingRequest(req, allowLan = false) {
  try {
    const protocol = req.socket.encrypted ? 'https:' : 'http:';
    const origin = new URL(req.headers.origin);
    if (origin.origin !== `${protocol}//${req.headers.host}`) return null;
    const host = origin.hostname;
    const localHost = host === 'localhost' || host === '[::1]' || host === '127.0.0.1';
    const privateHost = /^10\.\d+\.\d+\.\d+$/.test(host) || /^192\.168\.\d+\.\d+$/.test(host)
      || /^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$/.test(host) || /^\[(fc|fd|fe80:)/i.test(host);
    if (!localHost && !(allowLan && protocol === 'https:' && privateHost)) return null;
    if (!allowLan && !['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.socket.remoteAddress)) return null;
    const url = new URL(req.url, origin);
    if (url.pathname !== '/phone-signal') return null;
    const session = url.searchParams.get('session'), role = url.searchParams.get('role');
    if (!/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(session || '')) return null;
    if (!['desktop', 'phone'].includes(role)) return null;
    return {session, role};
  } catch { return null; }
}

export function attachPhoneSignaling(httpServer, WebSocketServer, allowLan = false) {
  const rooms = new Map();
  const wss = new WebSocketServer({noServer:true, maxPayload:64 * 1024});
  const upgrade = (req, socket, head) => {
    if (!req.url?.startsWith('/phone-signal')) return;
    const request = pairingRequest(req, allowLan);
    const reject = () => { socket.write('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n'); socket.destroy(); };
    if (!request) { reject(); return; }
    const {session, role} = request;
    const existing = rooms.get(session);
    if ((!existing && (role !== 'desktop' || rooms.size >= 4)) || existing?.has(role)) { reject(); return; }
    wss.handleUpgrade(req, socket, head, ws => {
      const room = existing || new Map(); rooms.set(session, room); room.set(role, ws);
      let alive = true, count = 0, windowStart = Date.now();
      ws.on('pong', () => { alive = true; });
      const heartbeat = setInterval(() => { if (!alive) ws.terminate(); else { alive = false; ws.ping(); } }, 30000);
      heartbeat.unref();
      ws.on('error', () => {}); // Oversized/malformed WebSocket frames must not crash Vite.
      ws.on('message', (data, binary) => {
        if (Date.now() - windowStart >= 1000) { count = 0; windowStart = Date.now(); }
        if (binary || ++count > 100) { ws.close(1008, 'Invalid signaling traffic'); return; }
        let msg;
        try { msg = JSON.parse(data.toString()); } catch { ws.close(1008); return; }
        if (!msg || !(['ice', role === 'phone' ? 'offer' : 'answer'].includes(msg.type))) { ws.close(1008); return; }
        for (const peer of room.values()) if (peer !== ws && peer.readyState === 1) {
          if (peer.bufferedAmount + data.length > 128 * 1024) peer.close(1008, 'Signaling buffer full');
          else peer.send(data, {binary:false});
        }
      });
      ws.on('close', () => {
        clearInterval(heartbeat); room.delete(role);
        if (!room.size) rooms.delete(session);
      });
    });
  };
  httpServer.on('upgrade', upgrade);
  const close = () => { httpServer.off('upgrade', upgrade); for (const ws of wss.clients) ws.terminate(); wss.close(); };
  httpServer.once('close', close);
  return close;
}
