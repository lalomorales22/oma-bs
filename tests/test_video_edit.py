"""Exercise real media output: trimming, audio removal, and original preservation."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from test_backend import load_backend


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class VideoEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.backend = load_backend(self.home)
        self.source = self.home / 'Videos/OMA-BS/original take.mp4'
        self.source.parent.mkdir(parents=True)
        subprocess.run([
            'ffmpeg', '-v', 'error', '-nostdin',
            '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=30:duration=2',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
            '-c:v', 'libx264', '-threads', '1', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-shortest', str(self.source),
        ], check=True, capture_output=True)
        self.original_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def assert_original_kept(self):
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.original_hash)
        self.assertEqual(list((self.source.parent / 'Exports').glob('.*.partial.mp4')), [])

    def test_trim_keeps_audio_and_lists_export(self):
        result = self.backend.export_video(str(self.source), 0.5, 1.5, False)
        info = self.backend.inspect_media(result['path'], thumbnail=False)
        self.assertAlmostEqual(info['duration'], 1.0, delta=0.12)
        self.assertTrue(info['hasAudio'])
        self.assertEqual((info['width'], info['height']), (160, 90))
        self.assertNotEqual(result['path'], str(self.source))
        self.assertIn(result['path'], [item['path'] for item in self.backend.media('video', 50)['items']])
        self.assert_original_kept()

    def test_mute_removes_audio_stream(self):
        result = self.backend.export_video(str(self.source), 0, 2, True)
        info = self.backend.inspect_media(result['path'], thumbnail=False)
        self.assertFalse(info['hasAudio'])
        self.assertAlmostEqual(info['duration'], 2.0, delta=0.12)
        self.assert_original_kept()

    def test_invalid_ranges_do_not_create_exports(self):
        for start, end in [(-1, 1), (1, 1), (1, 0), (0, 3), (2.01, 2.02), (float('nan'), 1), (0, float('inf'))]:
            with self.subTest(start=start, end=end), self.assertRaises(RuntimeError):
                self.backend.export_video(str(self.source), start, end, False)
        self.assertFalse((self.source.parent / 'Exports').exists())
        self.assert_original_kept()

    def test_encoder_failure_cleans_partial_output(self):
        popen = self.backend.subprocess.Popen
        def fail_encoder(command, **kwargs):
            # Simulate a damaged/incomplete encode, retaining real ffprobe calls.
            if command[0] == 'ffmpeg':
                Path(command[-1]).write_bytes(b'incomplete')
                return popen(['python3', '-c', 'raise SystemExit(1)'], **kwargs)
            return popen(command, **kwargs)
        with mock.patch.object(self.backend.subprocess, 'Popen', side_effect=fail_encoder):
            with self.assertRaisesRegex(RuntimeError, 'Export failed'):
                self.backend.export_video(str(self.source), 0, 1, False)
        self.assert_original_kept()
        self.assertEqual(list((self.source.parent / 'Exports').iterdir()), [])

    def test_thumbnail_and_media_metadata(self):
        with mock.patch.dict('os.environ', {'XDG_CACHE_HOME': str(self.home / 'cache')}):
            info = self.backend.inspect_media(str(self.source))
        self.assertEqual(info['kind'], 'video')
        self.assertTrue(info['thumbnail'].startswith((self.home / 'cache').as_uri()))
        self.assertTrue(info['hasAudio'])
        self.assert_original_kept()

    def test_hidden_partial_exports_are_not_in_gallery(self):
        folder = self.source.parent / 'Exports'
        folder.mkdir()
        (folder / '.pending.partial.mp4').write_bytes(b'partial')
        self.assertEqual([item['name'] for item in self.backend.media('video', 50)['items']], [self.source.name])

    def test_concurrent_export_cannot_overwrite_an_existing_file(self):
        popen = self.backend.subprocess.Popen
        existing = []
        def collision(command, **kwargs):
            if command[0] == 'ffmpeg':
                partial = Path(command[-1])
                output = partial.with_name(partial.name[1:].replace('.partial.mp4', '.mp4'))
                output.write_bytes(b'another export must survive')
                existing.append(output)
            return popen(command, **kwargs)
        with mock.patch.object(self.backend.subprocess, 'Popen', side_effect=collision):
            with self.assertRaises(FileExistsError):
                self.backend.export_video(str(self.source), 0, 1, False)
        self.assertEqual(existing[0].read_bytes(), b'another export must survive')
        self.assert_original_kept()
