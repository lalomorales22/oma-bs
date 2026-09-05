"""Native streaming tests use local listeners only, never real platform accounts."""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from test_backend import load_backend

FFMPEG = os.environ.get('OMA_BS_TEST_FFMPEG', shutil.which('ffmpeg') or '')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class StreamCommandTests(unittest.TestCase):
    def test_no_credentials_in_command_and_tls_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = load_backend(root)
            destination = {'id':'test', 'platform':'custom', 'url':'rtmps://example.test/private-app?token=secret-token', 'key':'secret-key'}
            command = backend.live_stream.network_command(destination, root, 'both')
            for secret in ('secret-key', 'secret-token', 'private-app'):
                self.assertNotIn(secret, repr(command))
            self.assertEqual(command[-1], 'rtmps://example.test')
            self.assertEqual(command[command.index('-tls_verify') + 1], '1')
            self.assertIn('rtmp_playpath=secret-key', (root / 'connection.ffpreset').read_text())
            self.assertEqual((root / 'connection.ffpreset').stat().st_mode & 0o777, 0o600)
            self.assertIn('amix=inputs=2', ' '.join(command))

    def test_capture_uses_one_h264_feed_and_separate_audio(self):
        with tempfile.TemporaryDirectory() as d:
            backend = load_backend(Path(d))
            args = argparse.Namespace(stream=True, audio='both', microphone='USB mic', fps=60, separate_audio=True)
            command = backend.capture_session.capture_command(args, 'portal', '/unused')
            self.assertNotIn('-o', command)
            self.assertEqual(command[command.index('-c') + 1], 'mpegts')
            self.assertEqual(command[command.index('-k') + 1], 'h264')
            self.assertEqual(command.count('-a'), 2)


@unittest.skipUnless(FFMPEG, 'FFmpeg required for local RTMP integration')
class NativeStreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backend = load_backend(self.root)
        self.config = self.root / 'config'; self.config.mkdir()
        self.bin = self.root / 'bin'; self.bin.mkdir()
        (self.bin / 'ffmpeg').symlink_to(FFMPEG)
        patch = mock.patch.dict(os.environ, {'PATH': str(self.bin) + os.pathsep + os.environ['PATH']})
        patch.start(); self.addCleanup(patch.stop)
        self.children = []
        self.broadcast = None
        self.addCleanup(self.cleanup)

    def child(self, command, **kwargs):
        proc = subprocess.Popen(command, **kwargs); self.children.append(proc); return proc

    def cleanup(self):
        if self.broadcast: self.broadcast.disable()
        for proc in self.children:
            if proc.poll() is None: proc.terminate()
        for proc in self.children:
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        if self.broadcast: self.broadcast.finish()
        for proc in self.children:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream: stream.close()

    def receiver(self, port, name):
        output = self.root / name
        self.child([FFMPEG, '-nostdin', '-v', 'error', '-listen', '1', '-i', f'rtmp://127.0.0.1:{port}/app/test-key',
                    '-c', 'copy', '-f', 'flv', str(output)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(.2)
        return output

    def source(self):
        return self.child([FFMPEG, '-nostdin', '-v', 'error', '-re', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=30',
                           '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
                           '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000',
                           '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'libx264', '-threads', '1',
                           '-preset', 'ultrafast', '-tune', 'zerolatency', '-g', '30', '-c:a', 'aac', '-f', 'mpegts', 'pipe:1'],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)

    def wait(self, predicate, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = self.broadcast.snapshot()
            if predicate(result): return result
            time.sleep(.1)
        self.fail('Local stream state: ' + repr(self.broadcast.snapshot()))

    def test_multiple_destinations_failure_isolation_and_stop_keeps_backup(self):
        good1, good2, bad = free_port(), free_port(), free_port()
        received = [self.receiver(good1, 'one.flv'), self.receiver(good2, 'two.flv')]
        source = self.source()
        destinations = [{'id':str(i), 'platform':'custom', 'url':f'rtmp://127.0.0.1:{port}/app', 'key':'test-key'}
                        for i, port in enumerate((good1, good2, bad))]
        backup = self.root / 'capture.ts'
        self.broadcast = self.backend.live_stream.Broadcast(source.stdout, backup, self.config, 'both', destinations)
        states = self.wait(lambda rows: sum(d['state'] == 'sending' for d in rows) == 2 and sum(d['state'] == 'failed' for d in rows) == 1)
        self.assertEqual(len(states), 3)
        self.broadcast.disable()
        before = backup.stat().st_size
        time.sleep(.7)
        self.assertGreater(backup.stat().st_size, before)
        self.assertEqual(self.broadcast.snapshot(), [])
        source.send_signal(signal.SIGINT); source.wait(timeout=5)
        self.broadcast.finish()
        self.assertEqual(list(self.config.glob('.stream-credentials-*')), [])
        for path in received:
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)], capture_output=True, check=True, text=True)
            streams = json.loads(probe.stdout)['streams']
            self.assertEqual([s['codec_type'] for s in streams].count('audio'), 1)
            self.assertTrue(any(s.get('codec_name') == 'h264' for s in streams))
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(backup)], capture_output=True, check=True, text=True)
        self.assertEqual(sum(s['codec_type'] == 'audio' for s in json.loads(probe.stdout)['streams']), 2)
