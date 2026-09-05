"""Use real, distinct tones to detect mixing or timing errors in source files."""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_backend import load_backend


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class AudioSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = load_backend(Path(self.temp.name))
        self.module = self.backend.capture_session.audio_sources
        self.preview = self.backend.VIDEO_DIR / 'test-take.mp4'
        self.folder = self.backend.VIDEO_DIR / 'Sources/test-take'
        self.folder.mkdir(parents=True)
        self.master = self.folder / 'capture.mkv'
        subprocess.run([
            'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=30:duration=2',
            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2',
            '-itsoffset', '0.3', '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000:duration=1.7',
            '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'libx264', '-threads', '1',
            '-c:a', 'aac', str(self.master),
        ], check=True, capture_output=True)
        self.original = hashlib.sha256(self.master.read_bytes()).hexdigest()
        self.args = argparse.Namespace(capture='display', audio='both', microphone='default_input', webcam=False)

    def samples(self, path):
        result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', '1',
                                 '-ar', '48000', '-f', 'f32le', '-'], capture_output=True, check=True)
        data = array.array('f')
        data.frombytes(result.stdout)
        return data

    def power(self, data, frequency):
        segment = data[24000:48000]
        sine = sum(value * math.sin(2 * math.pi * frequency * index / 48000) for index, value in enumerate(segment))
        cosine = sum(value * math.cos(2 * math.pi * frequency * index / 48000) for index, value in enumerate(segment))
        return sine * sine + cosine * cosine

    def test_isolated_tones_mixed_preview_and_offset_padding(self):
        manifest = self.module.finalize(self.backend, self.master, self.preview, self.args)
        desktop = self.samples(self.folder / 'desktop.flac')
        microphone = self.samples(self.folder / 'microphone.flac')
        mixed = self.samples(self.preview)
        self.assertGreater(self.power(desktop, 440), self.power(desktop, 880) * 100)
        self.assertGreater(self.power(microphone, 880), self.power(microphone, 440) * 100)
        self.assertGreater(self.power(mixed, 440), 100)
        self.assertGreater(self.power(mixed, 880), 100)
        self.assertLess(max(abs(value) for value in microphone[:9600]), .001)
        self.assertGreater(manifest['audioFiles'][1]['originalStartSeconds'], .25)
        self.assertEqual(hashlib.sha256(self.master.read_bytes()).hexdigest(), self.original)
        self.assertEqual(self.backend.inspect_media(str(self.preview), thumbnail=False)['sourcesFolder'], str(self.folder))
        self.assertEqual(json.loads((self.folder / 'session.json').read_text())['status'], 'ready')

    def test_wrong_track_count_keeps_master_and_marks_failure(self):
        self.args.audio = 'microphone'
        with self.assertRaisesRegex(RuntimeError, 'Expected 1 separate audio tracks, found 2'):
            self.module.finalize(self.backend, self.master, self.preview, self.args)
        self.assertFalse(self.preview.exists())
        self.assertFalse((self.folder / 'microphone.flac').exists())
        self.assertEqual(hashlib.sha256(self.master.read_bytes()).hexdigest(), self.original)
        self.assertEqual(json.loads((self.folder / 'session.json').read_text())['status'], 'failed')

    def test_existing_preview_is_never_overwritten(self):
        self.preview.write_bytes(b'existing video')
        with self.assertRaisesRegex(RuntimeError, 'refusing to overwrite'):
            self.module.finalize(self.backend, self.master, self.preview, self.args)
        self.assertEqual(self.preview.read_bytes(), b'existing video')
        self.assertEqual(hashlib.sha256(self.master.read_bytes()).hexdigest(), self.original)

    def test_single_input_and_silent_modes(self):
        for mode, track in [('microphone', '0:a:1'), ('desktop', '0:a:0'), ('none', None)]:
            with self.subTest(mode=mode):
                folder = self.backend.VIDEO_DIR / 'Sources' / mode
                folder.mkdir()
                source = folder / 'capture.mkv'
                preview = self.backend.VIDEO_DIR / (mode + '.mp4')
                command = ['ffmpeg', '-v', 'error', '-copyts', '-start_at_zero', '-i', str(self.master), '-map', '0:v:0']
                if track:
                    command += ['-map', track]
                command += ['-c', 'copy', str(source)]
                subprocess.run(command, check=True, capture_output=True)
                self.args.audio = mode
                result = self.module.finalize(self.backend, source, preview, self.args)
                self.assertEqual([entry['role'] for entry in result['audioFiles']], [mode] if track else [])
                self.assertEqual(self.backend.inspect_media(str(preview), thumbnail=False)['hasAudio'], bool(track))
