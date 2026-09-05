"""Owned native RTMP(S) fan-out. Network backpressure never blocks the backup."""
import os
import json
import signal
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import stream_settings


# Classify in memory and publish only fixed messages, never FFmpeg's raw output:
# server errors can contain a stream key, private app path, or ingest URL.
ERROR_TYPES = [
    ('ffmpeg_options', ('unrecognized option', 'option not found', 'error setting option', 'error reading preset'), 'FFmpeg rejected a streaming option or preset. Check the installed FFmpeg version and report this error category.'),
    ('authentication', ('authentication failed', 'authorization failed', 'unauthorized', '403 forbidden', 'invalid stream key', 'netstream.publish.badauth', 'netstream.publish.badname', 'server error: authentication'), 'The ingest server rejected publishing. Check account access, stream key, and whether another session is using it.'),
    ('tls', ('certificate verify failed', 'certificate verification failed', 'certificate is not trusted', 'certificate has expired', 'peer certificate', 'ssl handshake failed', 'tls handshake failed'), 'Secure connection failed during TLS verification or handshake. Check system time, CA certificates, and the RTMPS endpoint.'),
    ('dns', ('failed to resolve hostname', 'name or service not known', 'temporary failure in name resolution', 'getaddrinfo'), 'The ingest hostname could not be resolved. Check DNS and the server address.'),
    ('refused', ('connection refused',), 'The ingest server refused the connection. Check its port and whether your network permits it.'),
    ('timeout', ('connection timed out', 'operation timed out'), 'The ingest connection timed out. Check network access and the selected server.'),
    ('audio', ('matches no streams', 'cannot find a matching stream', 'invalid audio stream', 'error initializing complex filters'), 'FFmpeg could not find the expected media/audio tracks. Try desktop-only audio and check the saved source tracks.'),
    ('codec', ('codec not supported', 'not compatible with flv', 'codec is not supported', 'dimensions not set'), 'The captured media is not compatible with the streaming container. Check capture codec and dimensions.'),
    ('media', ('invalid data found when processing input', 'could not find codec parameters'), 'FFmpeg could not read the captured media. Check the local recording and capture engine.'),
    ('connection', ('connection reset by peer', 'broken pipe', 'input/output error'), 'The ingest connection ended. Check the platform dashboard and network connection.'),
]


def classify_error(text):
    lower = text.lower()
    return next(((code, message) for code, markers, message in ERROR_TYPES
                 if any(marker in lower for marker in markers)), None)


def ready_destinations(backend):
    destinations = stream_settings.load(backend)['destinations']
    if not destinations:
        raise RuntimeError('No destinations are saved. Add a channel in Stream and save it.')
    enabled = [d for d in destinations if d['enabled']]
    if not enabled:
        raise RuntimeError('Your saved destinations are disabled. Open Stream and choose Enable & save.')
    if any(not d['url'] or not d['key'] for d in enabled):
        raise RuntimeError('Every enabled destination needs a saved server URL and stream key.')
    return enabled


def check_ffmpeg(config_dir):
    result = subprocess.run(['ffmpeg', '-hide_banner', '-protocols'], capture_output=True, text=True, timeout=8)
    if result.returncode or 'rtmp' not in result.stdout.split() or 'rtmps' not in result.stdout.split():
        raise RuntimeError('Install FFmpeg with RTMP and RTMPS protocol support before streaming.')
    result = subprocess.run([transport_python(), str(transport_script()), '--check'], capture_output=True, timeout=65)
    if result.returncode:
        raise RuntimeError('Streaming transport needs gcc and FFmpeg headers. On Arch: sudo pacman -S --needed gcc ffmpeg')


def transport_script():
    return Path(__file__).resolve().parents[1] / 'studio/stream_transport.py'


def transport_python():
    # Use the stable system Python even when the user's shell uses mise.
    return os.environ.get('OMA_BS_TRANSPORT_PYTHON', '/usr/bin/python3')


def network_command(destination, folder, audio_mode):
    path = folder / 'connection.json'
    with open(path, 'x', opener=lambda p, f: os.open(p, f, 0o600)) as handle:
        json.dump({'url': destination['url'], 'key': destination['key']}, handle)
    return [transport_python(), str(transport_script()), str(path), audio_mode]


class Destination:
    def __init__(self, destination, config_dir, audio_mode):
        self.id, self.platform = destination['id'], destination['platform']
        self.state, self.reason = 'connecting', ''
        self.frames, self.last_progress, self.started = 0, 0, time.monotonic()
        self.bytes_sent, self.output_time = 0, 0
        self.input_started = 0
        self.closed = False
        self.error_code, self.error_message = '', ''
        self.stopped = threading.Event()
        self.chunks = queue.Queue(maxsize=32)  # At most 2 MiB per network destination.
        self.folder = tempfile.TemporaryDirectory(prefix='.stream-credentials-', dir=config_dir)
        self.proc = None
        try:
            command = network_command(destination, Path(self.folder.name), audio_mode)
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, bufsize=0, start_new_session=True)
        except Exception:
            self.folder.cleanup()
            raise RuntimeError('Could not start a stream destination. Check FFmpeg installation.') from None
        self.writer = threading.Thread(target=self.write, daemon=True)
        self.reader = threading.Thread(target=self.progress, daemon=True)
        self.error_reader = threading.Thread(target=self.read_errors, daemon=True)
        self.writer.start(); self.reader.start(); self.error_reader.start()

    def read_errors(self):
        pending = ''
        ranks = {code: index for index, (code, _, _) in enumerate(ERROR_TYPES)}
        while True:
            raw = self.proc.stderr.read(4096)
            if not raw: break
            pending = (pending + raw.decode(errors='replace'))[-8192:]
            result = classify_error(pending)
            if result and ranks[result[0]] < ranks.get(self.error_code, len(ranks)):
                self.error_code, self.error_message = result
        # Nothing raw is written to capture logs, notifications, or state.json.

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
                self.state, self.reason = 'failed', 'Stream worker exited without a recognized error. Report the destination error category and exit code.'
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
                self.state, self.reason = 'failed', 'Stream worker exited without a recognized error. Report the destination error category and exit code.'
            elif self.last_progress and now - self.last_progress > 15:
                self.state, self.reason = 'failed', 'Upload stalled. Recording continues locally.'
            elif self.input_started and not self.last_progress and now - self.input_started > 30:
                self.state, self.reason = 'failed', 'Connection timed out. Check the server URL and stream key.'
            if self.state == 'failed': self.close(failed=True)
        return {'id': self.id, 'platform': self.platform, 'state': self.state,
                'message': self.reason, 'bytes': self.bytes_sent,
                'errorCode': self.error_code if self.state == 'failed' else '',
                'exitCode': self.proc.poll()}

    def close(self, failed=False):
        if self.closed: return
        self.closed = True
        self.stopped.set()
        if self.proc.poll() is None:
            try: os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: self.proc.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL); self.proc.wait()
        # A converter can outlive a worker killed during a network write.
        try: os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        self.writer.join(timeout=1); self.reader.join(timeout=1); self.error_reader.join(timeout=1)
        if failed and self.error_message:
            self.reason = self.error_message
        self.proc.stdout.close()
        self.proc.stderr.close()
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
