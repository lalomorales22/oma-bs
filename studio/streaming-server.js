/**
 * OMA-BS relay server:
 *  1. Multistream: receives WebM over WebSocket, fans one FFmpeg encode out to
 *     every RTMP destination using independently bounded network workers.
 *  2. Kick chat helper: HTTP lookup of a channel's chatroom id (Kick blocks CORS).
 *  3. YouTube live chat: polls YouTube's internal live-chat endpoint and pushes
 *     messages to the browser (experimental, unofficial integration).
 *
 * Usage:  npm run relay   (requires FFmpeg on your PATH for streaming)
 */
import { createServer } from 'node:http';
import { WebSocketServer } from 'ws';
import { spawnSync } from 'node:child_process';
import { createRelay, localRequest } from './secure-relay.mjs';

const PORT = 4000;
const activeRelays = new Set();
const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36';

const ffmpegAvailable = !spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' }).error;
if (!ffmpegAvailable) {
  console.warn('⚠️  FFmpeg not found on PATH — chat features will work, but streaming will not.');
  console.warn('   Install it:  macOS: brew install ffmpeg   |   Windows: winget install ffmpeg');
}

// ---------------------------------------------------------------------------
// HTTP: Kick chatroom lookup (browser can't call kick.com directly — CORS)
// ---------------------------------------------------------------------------

const httpServer = createServer(async (req, res) => {
  if (!localRequest(req)) { res.writeHead(403); res.end(); return; }
  const match = req.url?.match(/^\/kick\/chatroom\/([\w-]+)$/);
  if (req.method === 'GET' && match) {
    try {
      const slug = match[1];
      const kickRes = await fetch(`https://kick.com/api/v2/channels/${slug}`, {
        headers: { 'User-Agent': UA, Accept: 'application/json' },
      });
      if (!kickRes.ok) throw new Error(`Kick API returned ${kickRes.status}`);
      const json = await kickRes.json();
      const chatroomId = json?.chatroom?.id;
      if (!chatroomId) throw new Error('No chatroom found for that channel.');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ chatroomId }));
    } catch (e) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(e.message || e) }));
    }
    return;
  }
  res.writeHead(404);
  res.end();
});

// ---------------------------------------------------------------------------
// YouTube live chat poller (innertube, experimental)
// ---------------------------------------------------------------------------

const startYouTubeChat = async (videoId, send, isAlive) => {
  const pageRes = await fetch(`https://www.youtube.com/live_chat?is_popout=1&v=${videoId}`, {
    headers: { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9' },
  });
  const page = await pageRes.text();

  const apiKey = page.match(/"INNERTUBE_API_KEY":"([^"]+)"/)?.[1];
  let continuation = page.match(/"continuation":"([^"]+)"/)?.[1];
  if (!apiKey || !continuation) {
    throw new Error('Could not find a live chat for that video — is the stream live with chat enabled?');
  }

  send({ type: 'youtube-chat-status', state: 'live' });

  while (isAlive() && continuation) {
    let timeoutMs = 4000;
    try {
      const res = await fetch(
        `https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key=${apiKey}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'User-Agent': UA },
          body: JSON.stringify({
            context: { client: { clientName: 'WEB', clientVersion: '2.20240401.00.00' } },
            continuation,
          }),
        },
      );
      const json = await res.json();
      const chat = json?.continuationContents?.liveChatContinuation;
      if (!chat) throw new Error('Chat ended.');

      const cont = chat.continuations?.[0];
      const contData =
        cont?.invalidationContinuationData ||
        cont?.timedContinuationData ||
        cont?.reloadContinuationData;
      continuation = contData?.continuation ?? null;
      timeoutMs = Math.max(2000, contData?.timeoutMs ?? 4000);

      const messages = [];
      for (const action of chat.actions ?? []) {
        const renderer = action?.addChatItemAction?.item?.liveChatTextMessageRenderer;
        if (!renderer) continue;
        const text = (renderer.message?.runs ?? [])
          .map((run) => run.text ?? run.emoji?.shortcuts?.[0] ?? '')
          .join('');
        if (text) {
          messages.push({ author: renderer.authorName?.simpleText ?? 'viewer', text });
        }
      }
      if (messages.length) send({ type: 'youtube-chat-messages', messages });
    } catch (e) {
      send({ type: 'youtube-chat-status', state: 'error', message: String(e.message || e) });
      return;
    }
    await new Promise((r) => setTimeout(r, timeoutMs));
  }
};

// ---------------------------------------------------------------------------
// WebSocket: multistream ingest + chat sessions
// ---------------------------------------------------------------------------

const wss = new WebSocketServer({ server: httpServer, maxPayload: 8 * 1024 * 1024,
  verifyClient: ({ req }) => localRequest(req) });

wss.on('connection', (ws) => {
  ws.on('error', () => {}); // Rejecting an oversized frame must not crash the relay.
  console.log('Client connected');

  let ffmpeg = null;
  let alive = true;
  let chatStarted = false;

  const send = (payload) => {
    try {
      ws.send(JSON.stringify(payload));
    } catch {
      /* socket may be closed */
    }
  };

  ws.on('message', (message, isBinary) => {
    if (isBinary) {
      if (ffmpeg) ffmpeg.write(message);
      return;
    }

    let config;
    try {
      config = JSON.parse(message.toString());
      if (!config || typeof config !== 'object' || Array.isArray(config)) throw new Error('Invalid configuration');
    } catch (e) {
      console.error('Invalid relay configuration');
      return;
    }

    // --- YouTube chat session
    if (config.type === 'youtube-chat') {
      if (chatStarted || typeof config.videoId !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(config.videoId)) return;
      chatStarted = true;
      console.log('Starting YouTube chat poller');
      startYouTubeChat(config.videoId, send, () => alive).catch((e) => {
        send({ type: 'youtube-chat-status', state: 'error', message: String(e.message || e) });
      });
      return;
    }

    // --- Multistream config
    if (ffmpeg) {
      send({ type: 'status', state: 'error', message: 'Stop the current broadcast before starting another.' });
      return;
    }
    const destinations = Array.isArray(config.destinations) ? config.destinations : config.url ? [config] : [];
    try {
      if (!ffmpegAvailable) throw new Error('FFmpeg is required for streaming.');
      ffmpeg = createRelay(destinations, send);
      activeRelays.add(ffmpeg);
      send({ type: 'status', state: 'live', destinations: destinations.map(() => 'Destination') });
    } catch {
      send({ type: 'status', state: 'error', message: 'Check your RTMP(S) URLs, keys, and FFmpeg installation.' });
    }
  });

  ws.on('close', () => {
    console.log('Client disconnected');
    alive = false;
    if (ffmpeg) {
      ffmpeg.close();
      activeRelays.delete(ffmpeg);
    }
  });
});

for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
  for (const relay of activeRelays) relay.close();
  for (const client of wss.clients) client.close();
  httpServer.close();
  setTimeout(() => process.exit(0), 2000).unref();
});

httpServer.listen(PORT, '127.0.0.1', () => {
  console.log(`🎥 OMA-BS Relay running on ws://localhost:${PORT}`);
  console.log('   • Multistream ingest (isolated FFmpeg destinations)');
  console.log('   • Kick chatroom lookup:  GET /kick/chatroom/:slug');
  console.log('   • YouTube live chat poller (experimental)');
});
