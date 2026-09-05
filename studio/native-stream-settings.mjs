import { lstat, readFile } from 'node:fs/promises';

// Read-only bridge for the explicitly launched local studio. Never enabled by
// the standalone/LAN dev server unless the native launcher supplies this path.
export const nativeStreamSettings = (settingsPath) => async (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  const reply = (status, value) => { res.statusCode = status; res.end(JSON.stringify(value)); };
  const host = req.headers.host || '';
  const origin = `${req.socket.encrypted ? 'https' : 'http'}://${host}`;
  if (!settingsPath) return reply(404, { error: 'Open the studio using OMA-BS on this device.' });
  if (req.method !== 'GET'
      || !['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.socket.remoteAddress)
      || !/^(127\.0\.0\.1|localhost|\[::1\])(:[0-9]+)?$/.test(host)
      || req.headers['x-oma-bs-request'] !== 'studio'
      || (req.headers.origin && req.headers.origin !== origin)
      || (req.headers['sec-fetch-site'] && req.headers['sec-fetch-site'] !== 'same-origin')) {
    return reply(403, { error: 'Open Stream settings in the local OMA-BS browser studio.' });
  }
  try {
    const info = await lstat(settingsPath);
    if (!info.isFile() || info.size > 65536 || (info.mode & 0o077)
        || (process.getuid && info.uid !== process.getuid())) throw new Error('Invalid file');
    const data = JSON.parse(await readFile(settingsPath, 'utf8'));
    if (data.version !== 1 || !Array.isArray(data.destinations) || data.destinations.length > 16) throw new Error('Invalid data');
    return reply(200, { version: 1, destinations: data.destinations });
  } catch {
    return reply(404, { error: 'Save destinations in the OMA-BS Stream tab first.' });
  }
};
