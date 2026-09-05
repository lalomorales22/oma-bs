"""Real composition output: pixels, timing, sound, and original preservation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import sys
from unittest import mock

from test_backend import load_backend
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import scene_editor


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class SceneEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.backend = load_backend(self.home)
        self.video = self.home / 'Videos/OMA-BS/blue.mp4'
        self.image = self.home / 'Pictures/OMA-BS/red.png'
        self.audio = self.home / 'Videos/OMA-BS/Sources/blue/microphone.flac'
        for path in (self.video, self.image, self.audio):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.ffmpeg('-f', 'lavfi', '-i', 'color=c=blue:s=160x90:r=30:d=2', '-c:v', 'libx264', '-threads', '1', str(self.video))
        self.ffmpeg('-f', 'lavfi', '-i', 'color=c=red:s=80x40', '-frames:v', '1', '-threads', '1', str(self.image))
        self.ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=880:duration=2', '-c:a', 'flac', str(self.audio))
        self.hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.video, self.image, self.audio)}

    def ffmpeg(self, *args):
        return subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', *args], check=True, capture_output=True).stdout

    def project(self, **kwargs):
        return {'version': 1, 'ratio': '16:9', 'duration': 1.5, 'base': {'path': str(self.video)}, 'layers': [], **kwargs}

    def render(self, project):
        result = scene_editor.render(self.backend, project, draft=True)
        for path, expected in self.hashes.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)
        self.assertFalse(list((self.video.parent / 'Exports').glob('.*.partial.mp4')))
        return result

    def pixel(self, path, at, x, y):
        data = self.ffmpeg('-ss', str(at), '-i', path, '-frames:v', '1', '-vf', f'crop=2:2:{x}:{y}', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-')
        return tuple(data[:3])

    def test_overlay_position_and_timeline_end(self):
        result = self.render(self.project(layers=[{'path': str(self.image), 'x': 0.5, 'y': 0.5, 'w': 0.4, 'h': 0.4, 'at': 0.5, 'length': 0.5}]))
        for at in (0.2, 1.2):
            red, green, blue = self.pixel(result['path'], at, 300, 180)
            self.assertGreater(blue, 220)
            self.assertLess(red, 25)
        red, green, blue = self.pixel(result['path'], 0.7, 300, 180)
        self.assertGreater(red, 220)
        self.assertLess(blue, 25)
        self.assertGreater(self.pixel(result['path'], 0.7, 50, 50)[2], 220)

    def test_all_canvas_shapes_and_still_image_base(self):
        for ratio, expected in scene_editor.DRAFTS.items():
            with self.subTest(ratio=ratio):
                result = self.render(self.project(ratio=ratio, duration=0.4, base={'path': str(self.image), 'fit': 'fit'}))
                info = self.backend.inspect_media(result['path'], thumbnail=False)
                self.assertEqual((info['width'], info['height']), expected)
                self.assertAlmostEqual(info['duration'], 0.4, delta=0.05)

    def test_audio_layer_delay_and_volume(self):
        result = self.render(self.project(layers=[{'path': str(self.audio), 'at': 0.5, 'length': 0.8, 'volume': 0.5}]))
        info = self.backend.inspect_media(result['path'], thumbnail=False)
        self.assertTrue(info['hasAudio'])
        def rms(start):
            raw = self.ffmpeg('-ss', str(start), '-i', result['path'], '-t', '0.15', '-vn', '-ac', '1', '-ar', '48000', '-f', 'f32le', '-')
            values = struct.unpack('<' + 'f' * (len(raw) // 4), raw)
            return (sum(v * v for v in values) / len(values)) ** 0.5
        self.assertLess(rms(0.1), 0.001)
        self.assertAlmostEqual(rms(0.7), 0.125 / (2 ** 0.5) * 0.5 / 0.95, delta=0.01)
        self.assertLess(rms(1.4), 0.001)

    def test_video_layer_can_be_trimmed_and_muted(self):
        result = self.render(self.project(layers=[{'path': str(self.video), 'mediaIn': 0.5, 'volume': 0, 'fit': 'fit'}]))
        self.assertFalse(self.backend.inspect_media(result['path'], thumbnail=False)['hasAudio'])

    def test_crop_pan_selects_the_requested_side(self):
        split = self.image.parent / 'split.png'
        self.ffmpeg('-f', 'lavfi', '-i', 'color=c=blue:s=160x80', '-vf', 'drawbox=x=80:y=0:w=80:h=80:color=red:t=fill', '-frames:v', '1', '-threads', '1', str(split))
        for pan, channel in ((0, 2), (1, 0)):
            with self.subTest(pan=pan):
                result = self.render(self.project(ratio='1:1', duration=0.3, base={'path': str(split), 'panX': pan}))
                self.assertGreater(self.pixel(result['path'], 0.1, 100, 100)[channel], 220)

    def test_project_save_load_and_rejected_save_keeps_previous(self):
        backend_path = Path(__file__).resolve().parents[1] / 'scripts/oma-bs'
        env = {**os.environ, 'OMA_BS_HOME': str(self.home), 'OMA_BS_CONFIG_DIR': str(self.home / '.config/oma-bs')}
        project = self.project()
        result = subprocess.run([str(backend_path), 'project-save', '--json', json.dumps(project)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        result = subprocess.run([str(backend_path), 'project-save', '--json', json.dumps(self.project(duration=100))], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        result = subprocess.run([str(backend_path), 'project-load'], env=env, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['project'], project)

    def test_invalid_edit_never_changes_sources_or_creates_output(self):
        cases = [self.project(ratio='3:7'), self.project(duration=float('nan')), self.project(duration=3),
                 self.project(base={'path': str(self.audio)}), self.project(layers=[{'path': str(self.image), 'x': 0.9}]),
                 self.project(layers=[{'path': str(self.audio), 'at': 2}]),
                 self.project(layers=[{'path': str(self.video), 'mediaIn': 3}]),
                 self.project(base={'path': '/etc/passwd'})]
        for project in cases:
            with self.subTest(project=project), self.assertRaises(RuntimeError):
                scene_editor.render(self.backend, project, draft=True)
        self.assertFalse((self.video.parent / 'Exports').exists())

    def test_audio_gallery_waveform_and_source_name(self):
        with mock.patch.dict('os.environ', {'XDG_CACHE_HOME': str(self.home / 'cache')}):
            listing = self.backend.media('audio', 50, thumbnails=True)
            info = self.backend.inspect_media(str(self.audio))
        self.assertEqual(len(listing['items']), 1)
        self.assertEqual(listing['items'][0]['name'], 'blue · microphone.flac')
        self.assertTrue(listing['items'][0]['thumbnail'].endswith('.wave.png'))
        self.assertEqual(info['kind'], 'audio')
        self.assertEqual(info['channels'], 1)
        self.assertAlmostEqual(info['duration'], 2, delta=0.05)

    def test_failed_encoder_removes_its_partial(self):
        popen = subprocess.Popen
        def fail(command, **kwargs):
            if command[0] == 'ffmpeg':
                Path(command[-1]).write_bytes(b'partial')
                return popen(['python3', '-c', 'raise SystemExit(1)'], **kwargs)
            return popen(command, **kwargs)
        with mock.patch.object(scene_editor.subprocess, 'Popen', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'Render failed'):
                scene_editor.render(self.backend, self.project(), True)
        self.assertEqual(list((self.video.parent / 'Exports').iterdir()), [])
