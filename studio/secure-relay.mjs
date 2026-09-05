import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

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
    preset: `rtmp_app=${parsed.pathname.replace(/^\/+|\/+$/g, '')}${parsed.search}\nrtmp_playpath=${key}\nrtmp_tcurl=${url.replace(/\/$/, '')}\n`,
    tls: parsed.protocol === 'rtmps:',
  };
}

// One CPU encode from the browser canvas; each destination only remuxes it.
// Destinations have bounded, independent buffers and private FFmpeg presets.
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
    if (!child || child.exitCode !== null || child.signalCode !== null) return;
    child.kill('SIGTERM');
    const timer = setTimeout(() => { if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL'); }, 1000);
    timer.unref();
  };
  function close() {
    if (closed) return;
    closed = true;
    stopChild(encoder);
    for (const w of workers) { clearInterval(w.timer); stopChild(w.child); }
    // Children load presets before accepting any media; keep them until exit.
    const pending = [encoder, ...workers.map(w => w.child)].filter(c => c && c.exitCode === null && c.signalCode === null);
    if (!pending.length) rmSync(folder, {recursive:true,force:true});
    else {
      let count = pending.length;
      for (const child of pending) child.once('close', () => { if (--count === 0) rmSync(folder, {recursive:true,force:true}); });
    }
  }
  try {
    for (const [index, spec] of specs.entries()) {
      const path = join(folder, `${index}.ffpreset`);
      writeFileSync(path, spec.preset, {mode:0o600,flag:'wx'});
      const args = ['-nostdin','-v','error','-stats_period','0.5','-progress','pipe:1','-protocol_whitelist','pipe','-f','mpegts','-i','pipe:0',
        '-map','0:v:0','-map','0:a?','-c','copy','-rw_timeout','8000000','-rtmp_live','live','-fpre',path];
      if (spec.tls) args.push('-tls_verify','1');
      const child = spawn('ffmpeg', [...args,'-f','flv',spec.endpoint], {stdio:['pipe','pipe','ignore']});
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
    encoder = spawn('ffmpeg', ['-nostdin','-v','error','-protocol_whitelist','pipe','-f','matroska','-i','pipe:0','-map','0:v:0','-map','0:a?',
      '-c:v','libx264','-threads','2','-preset','ultrafast','-tune','zerolatency','-maxrate','4000k','-bufsize','8000k',
      '-g','60','-c:a','aac','-b:a','160k','-ar','48000','-f','mpegts','pipe:1'], {stdio:['pipe','pipe','ignore']});
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
