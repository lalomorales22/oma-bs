import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

export function localRequest(req) {
  const host = req.headers.host || '';
  if (!['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.socket.remoteAddress)
      || !/^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$/.test(host)) return false;
  if (!req.headers.origin) return true; // Local Node proxy and CLI clients.
  try {
    const origin = new URL(req.headers.origin);
    return ['http:', 'https:'].includes(origin.protocol) && ['127.0.0.1', 'localhost', '[::1]'].includes(origin.hostname)
      && ['3000', '4173'].includes(origin.port);
  } catch { return false; }
}

export function destinationSpec(d) {
  if (!d || typeof d.url !== 'string' || typeof d.key !== 'string') throw new Error('Invalid destination');
  const url = d.url.trim(), key = d.key.trim();
  if (!key || url.length > 900 || key.length > 900 || /[\x00-\x1f\x7f]/.test(url + key)) throw new Error('Invalid destination');
  const parsed = new URL(url);
  if (!['rtmp:', 'rtmps:'].includes(parsed.protocol) || !parsed.hostname || parsed.username || parsed.password || parsed.hash) throw new Error('Use an RTMP or RTMPS ingest URL');
  return {
    endpoint: parsed.protocol + '//' + parsed.host,
    connection: JSON.stringify({url, key}),
    tls: parsed.protocol === 'rtmps:',
  };
}

// One CPU encode from the browser canvas; each destination only remuxes it.
// Destinations have bounded, independent buffers and private connection files.
export function createRelay(destinations, send) {
  if (!Array.isArray(destinations) || !destinations.length || destinations.length > 16) throw new Error('Choose 1–16 destinations');
  const specs = destinations.map(destinationSpec);
  const folder = mkdtempSync(join(tmpdir(), 'oma-bs-relay-'));
  let closed = false, confirmed = false, lastPartial = '', encoder;
  const workers = [];
  const notify = () => {
    if (closed) return;
    const good = workers.filter(w => w.sending && !w.failed).length;
    const failed = workers.filter(w => w.failed).length;
    if (failed === specs.length) {
      send({ type:'status', state:'error', message:'All destinations stopped. Check server URLs, keys, and upload connectivity.' });
      close();
    } else if (good === specs.length && !confirmed) {
      confirmed = true; send({ type:'status', state:'confirmed' });
    } else if (failed && lastPartial !== `${failed}:${good}`) {
      lastPartial = `${failed}:${good}`;
      send({ type:'status', state:'partial', sending:good, message:`${failed} destination(s) failed; ${good} sending. Check your channel dashboards.` });
    }
  };
  const stopChild = child => {
    if (!child || (!child.omaBsGroup && (child.exitCode !== null || child.signalCode !== null))) return;
    const kill = signal => {
      try { if (child.omaBsGroup && child.pid) process.kill(-child.pid, signal); else child.kill(signal); }
      catch (error) { if (error.code !== 'ESRCH') throw error; }
    };
    kill('SIGTERM');
    const timer = setTimeout(() => { if (child.omaBsGroup || (child.exitCode === null && child.signalCode === null)) kill('SIGKILL'); }, 1000);
    timer.unref();
  };
  function close() {
    if (closed) return;
    closed = true;
    stopChild(encoder);
    for (const w of workers) { clearInterval(w.timer); stopChild(w.child); }
    // Children load connection files before accepting media; keep them until exit.
    const pending = [encoder, ...workers.map(w => w.child)].filter(c => c && c.exitCode === null && c.signalCode === null);
    if (!pending.length) rmSync(folder, {recursive:true,force:true});
    else {
      let count = pending.length;
      for (const child of pending) child.once('close', () => { if (--count === 0) rmSync(folder, {recursive:true,force:true}); });
    }
  }
  try {
    for (const [index, spec] of specs.entries()) {
      const path = join(folder, `${index}.json`);
      writeFileSync(path, spec.connection, {mode:0o600,flag:'wx'});
      const child = spawn(process.env.OMA_BS_TRANSPORT_PYTHON || '/usr/bin/python3',
        [fileURLToPath(new URL('./stream_transport.py', import.meta.url)), path, 'ready'], {stdio:['pipe','pipe','ignore'],detached:true});
      child.omaBsGroup = true;
      const w = {child,failed:false,sending:false,started:0,last:0,time:0,size:0,buffer:'',timer:null};
      workers.push(w);
      const fail = () => { if (!closed && !w.failed) { w.failed = true; clearInterval(w.timer); stopChild(child); notify(); } };
      child.on('error', fail); child.on('close', fail); child.stdin.on('error', fail);
      child.stdout.on('data', chunk => {
        w.buffer += chunk.toString();
        const lines = w.buffer.split('\n'); w.buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('total_size=')) w.size = Number(line.slice(11));
          if (line.startsWith('out_time_us=') && Number(line.slice(12)) > w.time && w.size > 1024) {
            w.time = Number(line.slice(12)); w.last = Date.now(); w.sending = true; notify();
          }
        }
      });
      w.timer = setInterval(() => {
        if (w.last && Date.now() - w.last > 15000) fail();
        else if (w.started && !w.last && Date.now() - w.started > 30000) fail();
      }, 1000); w.timer.unref();
      w.push = data => {
        if (closed || w.failed) return;
        if (!w.started) w.started = Date.now();
        if (child.stdin.writableLength + data.length > 2 * 1024 * 1024) { fail(); return; }
        child.stdin.write(data);
      };
    }
    const encoderEnv = {...process.env}; delete encoderEnv.FFREPORT;
    encoder = spawn('ffmpeg', ['-nostdin','-v','error','-protocol_whitelist','pipe','-f','matroska','-i','pipe:0','-map','0:v:0','-map','0:a?',
      '-c:v','libx264','-threads','2','-preset','ultrafast','-tune','zerolatency','-maxrate','4000k','-bufsize','8000k',
      '-g','60','-c:a','aac','-b:a','160k','-ar','48000','-f','mpegts','pipe:1'], {stdio:['pipe','pipe','ignore'],env:encoderEnv});
    encoder.stdout.on('data', data => { for (const w of workers) w.push(data); });
    encoder.stdin.on('error', () => {});
    encoder.on('error', () => { send({type:'status',state:'error',message:'Could not start FFmpeg.'}); close(); });
    encoder.on('close', code => { if (!closed) { send({type:'status',state:'stopped',code}); close(); } });
  } catch {
    close(); throw new Error('Could not prepare the local stream relay.');
  }
  return {
    write(data) {
      if (closed) return;
      if (encoder.stdin.writableLength + data.length > 8 * 1024 * 1024) {
        send({type:'status',state:'error',message:'Browser upload exceeded the relay buffer. Local archive remains available.'}); close(); return;
      }
      encoder.stdin.write(data);
    }, close,
  };
}
