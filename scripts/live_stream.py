"""Owned native RTMP(S) fan-out. Network backpressure never blocks the backup."""
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit
import stream_settings


def ready_destinations(backend):
    destinations = stream_settings.load(backend)['destinations']
    enabled = [d for d in destinations if d['enabled']]
    if not enabled:
        raise RuntimeError('Add and enable a destination in Stream, then save it first.')
    if any(not d['url'] or not d['key'] for d in enabled):
        raise RuntimeError('Every enabled destination needs a saved server URL and stream key.')
    return enabled


def check_ffmpeg(config_dir):
    result = subprocess.run(['ffmpeg', '-hide_banner', '-protocols'], capture_output=True, text=True, timeout=8)
    if result.returncode or 'rtmp' not in result.stdout.split() or 'rtmps' not in result.stdout.split():
        raise RuntimeError('Install FFmpeg with RTMP and RTMPS protocol support before streaming.')


def network_command(destination, folder, audio_mode):
    parsed = urlsplit(destination['url'])
    host = parsed.hostname
    if ':' in host:
        host = '[' + host + ']'
    endpoint = parsed.scheme + '://' + host + (':' + str(parsed.port) if parsed.port else '')
    app = parsed.path.strip('/') + ('?' + parsed.query if parsed.query else '')
    values = {'rtmp_app': app, 'rtmp_playpath': destination['key'], 'rtmp_tcurl': destination['url'].rstrip('/')}
    if any(len(value) > 900 for value in values.values()):
        raise RuntimeError('Native streaming supports server URLs and keys up to 900 characters.')
    # FFmpeg presets apply protocol AVOptions without putting their values in argv.
    path = folder / 'connection.ffpreset'
    with open(path, 'x', opener=lambda p, f: os.open(p, f, 0o600)) as handle:
        handle.write(''.join(name + '=' + value + '\n' for name, value in values.items()))
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-stats_period', '0.5',
               '-progress', 'pipe:1', '-f', 'mpegts', '-i', 'pipe:0']
    if audio_mode == 'none':
        command += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-map', '0:v:0', '-map', '1:a:0', '-shortest']
    elif audio_mode == 'both':
        command += ['-filter_complex', '[0:a:0][0:a:1]amix=inputs=2:normalize=1:duration=longest[a]', '-map', '0:v:0', '-map', '[a]']
    else:
        command += ['-map', '0:v:0', '-map', '0:a:0']
    command += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000',
                '-rw_timeout', '8000000', '-rtmp_live', 'live',
                '-fpre', str(path)]
    if parsed.scheme == 'rtmps':
        command += ['-tls_verify', '1']
    return command + ['-f', 'flv', endpoint]


class Destination:
    def __init__(self, destination, config_dir, audio_mode):
        self.id, self.platform = destination['id'], destination['platform']
        self.state, self.reason = 'connecting', ''
        self.frames, self.last_progress, self.started = 0, 0, time.monotonic()
        self.bytes_sent, self.output_time = 0, 0
        self.input_started = 0
        self.closed = False
        self.stopped = threading.Event()
        self.chunks = queue.Queue(maxsize=32)  # At most 2 MiB per network destination.
        self.folder = tempfile.TemporaryDirectory(prefix='.stream-credentials-', dir=config_dir)
        self.proc = None
        try:
            command = network_command(destination, Path(self.folder.name), audio_mode)
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, bufsize=0)
        except Exception:
            self.folder.cleanup()
            raise RuntimeError('Could not start a stream destination. Check FFmpeg installation.') from None
        self.writer = threading.Thread(target=self.write, daemon=True)
        self.reader = threading.Thread(target=self.progress, daemon=True)
        self.writer.start(); self.reader.start()

    def progress(self):
        for raw in self.proc.stdout:
            key, _, value = raw.decode(errors='replace').strip().partition('=')
            if key in ('total_size', 'out_time_us'):
                try:
                    amount = int(value)
                    if key == 'total_size': self.bytes_sent = max(self.bytes_sent, amount)
                    elif amount > self.output_time:
                        self.output_time = amount
                        if self.bytes_sent > 1024:
                            self.last_progress = time.monotonic()
                            if not self.stopped.is_set(): self.state = 'sending'
                except ValueError: pass
            if key == 'frame':
                try:
                    frame = int(value)
                    if frame > self.frames:
                        self.frames = frame
                        self.last_progress = time.monotonic()
                        if not self.stopped.is_set(): self.state = 'sending'
                except ValueError:
                    pass

    def write(self):
        try:
            while not self.stopped.is_set():
                try: data = self.chunks.get(timeout=.1)
                except queue.Empty: continue
                view = memoryview(data)
                while view and not self.stopped.is_set():
                    count = self.proc.stdin.write(view)
                    if not count: raise BrokenPipeError()
                    view = view[count:]
        except (OSError, ValueError):
            if not self.stopped.is_set():
                self.state, self.reason = 'failed', 'Connection ended. Check this destination’s dashboard and credentials.'
        finally:
            try: self.proc.stdin.close()
            except OSError: pass

    def feed(self, data):
        if self.stopped.is_set() or self.state == 'failed': return
        if not self.input_started: self.input_started = time.monotonic()
        try: self.chunks.put_nowait(data)
        except queue.Full:
            self.state, self.reason = 'failed', 'Upload could not keep up. Other destinations and the backup continue.'
            self.stopped.set()
            if self.proc.poll() is None: self.proc.terminate()

    def poll(self):
        if self.state == 'failed' and not self.closed: self.close(failed=True)
        if self.state not in ('failed', 'off'):
            now = time.monotonic()
            if self.proc.poll() is not None:
                self.state, self.reason = 'failed', 'Connection ended. Check this destination’s dashboard and credentials.'
            elif self.last_progress and now - self.last_progress > 15:
                self.state, self.reason = 'failed', 'Upload stalled. Recording continues locally.'
            elif self.input_started and not self.last_progress and now - self.input_started > 30:
                self.state, self.reason = 'failed', 'Connection timed out. Check the server URL and stream key.'
            if self.state == 'failed': self.close(failed=True)
        return {'id': self.id, 'platform': self.platform, 'state': self.state,
                'message': self.reason, 'bytes': self.bytes_sent}

    def close(self, failed=False):
        if self.closed: return
        self.closed = True
        self.stopped.set()
        if self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                self.proc.kill(); self.proc.wait()
        self.writer.join(timeout=1); self.reader.join(timeout=1)
        self.proc.stdout.close()
        self.folder.cleanup()
        if not failed: self.state = 'off'


class Broadcast:
    def __init__(self, source, backup, config_dir, audio_mode, destinations):
        self.source, self.backup = source, backup
        self.config_dir, self.audio_mode = config_dir, audio_mode
        self.outputs, self.error = [], ''
        self.lock = threading.Lock()
        self.enable(destinations)
        self.thread = threading.Thread(target=self.pump, daemon=True)
        self.thread.start()

    def enable(self, destinations):
        self.disable()
        new = []
        try:
            for d in destinations: new.append(Destination(d, self.config_dir, self.audio_mode))
        except Exception:
            for worker in new: worker.close()
            raise
        with self.lock: self.outputs = new

    def disable(self):
        with self.lock:
            old, self.outputs = self.outputs, []
        for worker in old: worker.close()

    def pump(self):
        try:
            with self.backup.open('xb') as saved:
                while True:
                    data = self.source.read(65536)
                    if not data: break
                    saved.write(data); saved.flush()
                    with self.lock:
                        for worker in self.outputs: worker.feed(data)
        except Exception:
            self.error = 'Could not keep the local stream backup. Capture has been stopped.'

    def snapshot(self):
        with self.lock: outputs = list(self.outputs)
        return [worker.poll() for worker in outputs]

    def finish(self):
        self.disable()
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise RuntimeError('Backup pipe did not finish. The transport file has been kept.')
        if self.error: raise RuntimeError(self.error)


def remux_backup(transport, master):
    result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-i', str(transport),
                             '-map', '0:v:0', '-map', '0:a?', '-c', 'copy', str(master)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
    if result.returncode:
        raise RuntimeError('Backup conversion failed. The original capture.ts is kept in the take’s source folder.')
