import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_backend(home: Path):
    os.environ["OMA_BS_HOME"] = str(home)
    path = Path(__file__).parents[1] / "scripts" / "oma-bs"
    loader = importlib.machinery.SourceFileLoader("oma_bs_backend", str(path))
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.backend = load_backend(self.home)

    def tearDown(self):
        self.temp.cleanup()

    def test_default_config(self):
        value = self.backend.config()
        self.assertEqual(value["capture"], "window")
        self.assertEqual(value["audio"], "both")
        self.assertTrue(value["saveSeparateTracks"])

    def test_process_info_reads_current_process(self):
        proc_self_pid = int(Path('/proc/self/stat').read_text().split(' ', 1)[0])
        if proc_self_pid != os.getpid():
            self.skipTest('Runtime PID namespace does not match mounted /proc; requires host smoke test')
        info = self.backend.process_info(os.getpid())
        if info is None:
            self.skipTest('Runtime PID namespace does not match mounted /proc; requires host smoke test')
        self.assertEqual(info['pid'], os.getpid())
        self.assertTrue(info['alive'])
        self.assertEqual(info['session'], os.getsid(0))

    def test_process_info_parses_session_and_start_time(self):
        folder = mock.MagicMock()
        folder.stat.return_value.st_uid = os.getuid()
        stat_file = mock.Mock()
        stat_file.read_text.return_value = '123 (mpv camera) ' + ' '.join(['S', '1', '123', '123'] + ['0'] * 15 + ['9876'])
        cmd_file = mock.Mock()
        cmd_file.read_bytes.return_value = b'mpv\0--title=WebcamOverlay\0av://v4l2:/dev/video0\0'
        folder.__truediv__.side_effect = lambda name: stat_file if name == 'stat' else cmd_file
        with mock.patch.object(self.backend, 'Path') as path:
            path.return_value.__truediv__.return_value = folder
            info = self.backend.process_info(123)
        self.assertEqual(info['session'], 123)
        self.assertEqual(info['ticks'], '9876')
        self.assertTrue(info['alive'])

    def test_overlay_match_does_not_match_regular_mpv(self):
        self.assertFalse(self.backend.is_overlay({'args': ['mpv', '/tmp/movie.mp4']}))
        self.assertFalse(self.backend.is_overlay({'args': ['other-player', '--title=WebcamOverlay', 'av://v4l2:/dev/video0']}))
        self.assertTrue(self.backend.is_overlay({'args': ['/usr/bin/mpv', '--title=WebcamOverlay', 'av://v4l2:/dev/video0']}))

    def test_stop_closes_leftover_camera_when_recorder_is_gone(self):
        with mock.patch.object(self.backend, 'require'), mock.patch.object(self.backend, 'is_recording', return_value=False), mock.patch.object(self.backend, 'webcam_off', return_value={'ok': True, 'message': 'Closed'}) as off:
            self.assertTrue(self.backend.stop()['ok'])
            off.assert_called_once()

    def test_pending_picker_does_not_trigger_camera_cleanup(self):
        self.backend.write_json(self.backend.STATE_FILE, {'phase': 'starting', 'sessionPid': 123, 'launcherTicks': '42'})
        with mock.patch.object(self.backend, 'is_recording', return_value=False), mock.patch.object(self.backend, 'process_info', return_value={'alive': True, 'ticks': '42'}), mock.patch.object(self.backend, 'overlays', return_value=[]), mock.patch.object(self.backend, 'close_overlays') as close:
            result = self.backend.status()
            self.assertTrue(result['starting'])
            close.assert_not_called()

    def test_unexpected_exit_closes_tracked_camera(self):
        camera = {'pid': 456, 'ticks': '43'}
        self.backend.write_json(self.backend.STATE_FILE, {'phase': 'recording', 'sawCapture': True, 'sessionPid': 123, 'cameras': [camera]})
        with mock.patch.object(self.backend, 'is_recording', return_value=False), mock.patch.object(self.backend, 'process_info', return_value=None), mock.patch.object(self.backend, 'overlays', return_value=[]), mock.patch.object(self.backend, 'close_overlays') as close:
            result = self.backend.status()
            self.assertEqual(result['state']['phase'], 'ended')
            close.assert_called_once_with([camera])

    def test_reused_pid_is_not_signalled(self):
        with mock.patch.object(self.backend.os, 'pidfd_open', return_value=9), mock.patch.object(self.backend.os, 'close'), mock.patch.object(self.backend, 'process_info', return_value={'ticks': 'NEW'}), mock.patch.object(self.backend.signal, 'pidfd_send_signal') as send:
            self.assertEqual(self.backend.close_overlays([{'pid': 123, 'ticks': 'OLD'}]), 0)
            send.assert_not_called()

    def test_media_is_newest_first(self):
        folder = self.home / "Videos" / "OMA-BS"
        folder.mkdir(parents=True)
        old = folder / "old.mp4"
        new = folder / "new.webm"
        old.write_bytes(b"old")
        new.write_bytes(b"new")
        os.utime(old, (1, 1))
        os.utime(new, (2, 2))
        result = self.backend.media("video", 10)
        self.assertEqual([item["name"] for item in result["items"]], ["new.webm", "old.mp4"])

    def test_rejects_untrusted_open_path(self):
        outside = self.home / "secret.txt"
        outside.write_text("nope")
        with self.assertRaisesRegex(RuntimeError, "outside"):
            self.backend.safe_media_path(str(outside))

if __name__ == "__main__":
    unittest.main()
