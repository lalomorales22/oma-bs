"""Run the real supervisor against simulated recorder/camera executables.

This exercises OS process lifetime and file locks without a Wayland desktop.
Media output is a real FFmpeg fixture; GPU/portal/device behavior needs host QA.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from test_backend import load_backend


class CaptureCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = load_backend(Path(self.temp.name))
        self.capture = self.backend.capture_session

    def test_selected_input_is_one_argument_and_no_global_default_change(self):
        args = argparse.Namespace(audio='both', microphone='USB mic with spaces', fps=30)
        command = self.capture.capture_command(args, 'DP-1', '/tmp/a file.mp4')
        self.assertEqual(command[command.index('-a') + 1], 'default_output|USB mic with spaces')
        self.assertEqual(command[command.index('-f') + 1], '30')
        self.assertNotIn('pactl', command)

    def test_audio_modes(self):
        for mode, value in [('none', None), ('desktop', 'default_output'), ('microphone', 'usb_mic')]:
            command = self.capture.capture_command(argparse.Namespace(audio=mode, microphone='usb_mic', fps=60), 'portal', '/tmp/a.mp4')
            if value is None:
                self.assertNotIn('-a', command)
            else:
                self.assertEqual(command[command.index('-a') + 1], value)

    def test_device_parser_excludes_monitor_sources_and_metadata_nodes(self):
        with mock.patch.object(self.capture, 'output', side_effect=[
                'default_input|Default\nalsa_input.usb|USB Mic\nalsa_output.x.monitor|Monitor\n',
                '/dev/video0  USB Camera\n/dev/other  Metadata\n']):
            data = self.capture.devices()
        self.assertEqual([m['id'] for m in data['microphones']], ['default_input', 'alsa_input.usb'])
        self.assertEqual(data['cameras'], [{'id': '/dev/video0', 'label': 'USB Camera'}])

    def test_missing_selected_device_fails_without_substitution(self):
        args = self.backend.parser().parse_args(['start', '--microphone', 'unplugged'])
        with mock.patch.object(self.capture, 'devices', return_value={'microphones': [], 'cameras': []}):
            with self.assertRaisesRegex(RuntimeError, 'microphone is unavailable'):
                self.capture.validate_settings(args)

    def test_region_overlay_stays_inside_negative_coordinate_capture(self):
        for size in ['small', 'medium', 'large']:
            width, height, x, y = self.capture.region_overlay_geometry('250x600+-300+-20', size)
            self.assertGreaterEqual(x, -300)
            self.assertGreaterEqual(y, -20)
            self.assertLessEqual(x + width, -50)
            self.assertLessEqual(y + height, 580)

    def test_foreign_recorder_is_not_stopped(self):
        with mock.patch.object(self.backend, 'require'), mock.patch.object(self.backend, 'is_recording', return_value=True), mock.patch.object(self.backend.subprocess, 'run') as run:
            result = self.backend.stop()
        self.assertFalse(result['ok'])
        run.assert_not_called()


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bin = self.home / 'bin'
        self.bin.mkdir()
        self.backend = Path(__file__).parents[1] / 'scripts/oma-bs'
        self.env = {**os.environ, 'OMA_BS_HOME': str(self.home),
                    'OMA_BS_CONFIG_DIR': str(self.home / '.config/oma-bs'),
                    'OMA_BS_VIDEO_DIR': str(self.home / 'Videos/OMA-BS'),
                    'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'OMA_TEST_CAMERA_MARKER': str(self.home / 'camera')}
        self.fixture = self.home / 'fixture.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'testsrc2=size=160x90:rate=30:duration=1', '-c:v', 'libx264',
                        '-threads', '1', str(self.fixture)], check=True, capture_output=True)
        self.env['OMA_TEST_FIXTURE'] = str(self.fixture)
        self.program('gpu-screen-recorder', '''
import json, os, shutil, signal, sys, time
from pathlib import Path
if '--list-audio-devices' in sys.argv:
    print('alsa_input.usb|USB Microphone')
    raise SystemExit(0)
Path(os.environ['OMA_BS_HOME'], 'recorder-args.json').write_text(json.dumps(sys.argv))
destination = sys.argv[sys.argv.index('-o') + 1]
shutil.copyfile(os.environ['OMA_TEST_FIXTURE'], destination)
signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
started = time.monotonic()
while True:
    if os.environ.get('OMA_TEST_CRASH') and time.monotonic() - started > .4:
        raise SystemExit(7)
    time.sleep(.05)
''')
        self.program('mpv', '''
import os, signal, sys, time
from pathlib import Path
p = Path(os.environ['OMA_TEST_CAMERA_MARKER'])
p.write_text('open')
Path(str(p) + '.pid').write_text(str(os.getpid()))
def stop(*_):
    p.write_text('closed')
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
while True: time.sleep(.05)
''')
        self.program('omarchy-capture-webcam-list', "print('/dev/video0  USB Camera')")
        self.program('omarchy-hyprland-monitor-focused', "print('DP-1')")
        self.program('hyprctl', '''
import json, os, sys
from pathlib import Path
if 'clients' in sys.argv:
    p = Path(os.environ['OMA_TEST_CAMERA_MARKER'] + '.pid')
    print(json.dumps([{'pid':int(p.read_text()), 'title':'WebcamOverlay', 'address':'0xabc'}] if p.exists() else []))
else:
    print('[ {"focused":true,"width":1920,"height":1080} ]')
''')
        self.program('omarchy-notification-send', 'pass')
        self.program('omarchy-capture-region', '''
import time
time.sleep(30)
''')
        self.addCleanup(self.stop_if_needed)

    def program(self, name, code):
        path = self.bin / name
        path.write_text('#!' + sys.executable + '\n' + code)
        path.chmod(0o755)

    def test_native_stream_toggle_keeps_owned_capture_and_saves_sources(self):
        self.program('gpu-screen-recorder', '''
import os, sys
if '--list-audio-devices' in sys.argv:
    print('alsa_input.usb|USB Microphone'); raise SystemExit(0)
os.execvp('ffmpeg', ['ffmpeg', '-nostdin', '-v', 'error', '-re', '-stream_loop', '-1', '-i', os.environ['OMA_TEST_FIXTURE'],
    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000',
    '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'copy', '-c:a', 'aac', '-f', 'mpegts', 'pipe:1'])
''')
        settings = self.home / '.config/oma-bs/streaming.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'version':1,'destinations':[{'id':'local-test','platform':'custom',
            'url':'rtmp://127.0.0.1:1/app','key':'fake-test-key','enabled':True}]}))
        self.assertTrue(self.cli('start-stream', '--capture', 'display', '--audio', 'both', '--webcam')['ok'])
        first = self.wait_phase({'recording'})
        self.assertTrue(first['streamCapable'])
        self.assertTrue(first['broadcastEnabled'])
        token = first['state']['token']
        self.cli('stop-stream')
        for _ in range(60):
            status = self.cli('status')
            if not status['broadcastEnabled']: break
            time.sleep(.05)
        self.assertFalse(status['broadcastEnabled'])
        self.assertTrue(status['recording'])
        self.assertTrue(status['cameraOpen'])
        self.assertTrue(self.cli('start-stream')['ok'])
        for _ in range(60):
            status = self.cli('status')
            if status['broadcastEnabled']: break
            time.sleep(.05)
        self.assertTrue(status['broadcastEnabled'])
        self.assertEqual(status['state']['token'], token)
        self.cli('stop')
        final = self.wait_phase({'stopped'}, timeout=12)
        self.assertFalse(final['broadcastEnabled'])
        folder = Path(final['state']['sourcesFolder'])
        for name in ('capture.ts', 'capture.mkv', 'desktop.flac', 'microphone.flac'):
            self.assertGreater((folder / name).stat().st_size, 0)
        self.assertEqual((self.home / 'camera').read_text(), 'closed')
        self.assertEqual(list(settings.parent.glob('.stream-credentials-*')), [])
        self.assertNotIn('fake-test-key', (settings.parent / 'capture.log').read_text())

    def cli(self, *args):
        result = subprocess.run([sys.executable, str(self.backend), *args], env=self.env,
                                capture_output=True, text=True, timeout=10)
        return json.loads(result.stdout)

    def wait_phase(self, phases, timeout=6):
        end = time.monotonic() + timeout
        last = {}
        while time.monotonic() < end:
            last = self.cli('status')
            if last['state'].get('phase') in phases:
                return last
            time.sleep(.05)
        log = self.home / '.config/oma-bs/capture.log'
        self.fail(f'No phase {phases}: {last}; log={log.read_text() if log.exists() else ""}')

    def stop_if_needed(self):
        try:
            self.cli('stop')
            self.wait_phase({'stopped', 'ended'}, timeout=4)
        except Exception:
            pass

    def test_camera_off_keeps_recording_and_other_camera_alive(self):
        other_env = {**self.env, 'OMA_TEST_CAMERA_MARKER': str(self.home / 'other-camera')}
        other = subprocess.Popen([str(self.bin / 'mpv'), '--title=WebcamOverlay'], env=other_env)
        self.addCleanup(lambda: (other.terminate(), other.wait()) if other.poll() is None else None)
        result = self.cli('start', '--capture', 'display', '--webcam', '--microphone', 'alsa_input.usb', '--fps', '30')
        self.assertTrue(result['ok'])
        self.assertTrue(self.wait_phase({'recording'})['cameraOpen'])
        self.assertTrue(self.cli('webcam-off')['ok'])
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and (self.home / 'camera').read_text() != 'closed':
            time.sleep(.05)
        self.assertEqual((self.home / 'camera').read_text(), 'closed')
        self.assertTrue(self.cli('status')['recording'])
        self.assertIsNone(other.poll())
        self.cli('stop')
        state = self.wait_phase({'stopped'})['state']
        self.assertTrue(Path(state['lastFile']).is_file())
        command = json.loads((self.home / 'recorder-args.json').read_text())
        self.assertEqual(command[command.index('-a') + 1], 'default_output|alsa_input.usb')
        config = json.loads((self.home / '.config/oma-bs/config.json').read_text())
        self.assertFalse(config['webcam'])

    def test_unexpected_exit_closes_camera_without_status_polling(self):
        self.env['OMA_TEST_CRASH'] = '1'
        self.assertTrue(self.cli('start', '--capture', 'display', '--webcam')['ok'])
        # Deliberately don't call status: the supervisor must clean up itself.
        marker = self.home / 'camera'
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if marker.exists() and marker.read_text() == 'closed':
                break
            time.sleep(.05)
        self.assertEqual(marker.read_text(), 'closed')
        state = self.wait_phase({'ended'})['state']
        self.assertEqual(state['exitCode'], 7)
        self.assertTrue(Path(state['lastFile']).exists())

    def test_double_start_is_rejected_and_picker_can_be_cancelled(self):
        self.assertTrue(self.cli('start', '--capture', 'region')['ok'])
        self.assertFalse(self.cli('start', '--capture', 'display')['ok'])
        self.assertTrue(self.cli('stop')['ok'])
        self.wait_phase({'stopped'})
        self.assertFalse((self.home / 'recorder-args.json').exists())

    def test_stop_also_closes_camera_and_does_not_require_popup(self):
        self.assertTrue(self.cli('start', '--capture', 'display', '--webcam')['ok'])
        self.wait_phase({'recording'})
        self.cli('stop')
        self.wait_phase({'stopped'})
        self.assertEqual((self.home / 'camera').read_text(), 'closed')

    def test_separate_audio_session_publishes_sources_and_preview(self):
        multitrack = self.home / 'multitrack.mkv'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(self.fixture),
                        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
                        '-f', 'lavfi', '-i', 'sine=frequency=880:duration=1',
                        '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'copy',
                        '-c:a', 'aac', str(multitrack)], check=True, capture_output=True)
        self.env['OMA_TEST_FIXTURE'] = str(multitrack)
        self.assertTrue(self.cli('start', '--capture', 'display', '--separate-audio')['ok'])
        self.wait_phase({'recording'})
        self.cli('stop')
        state = self.wait_phase({'stopped'})['state']
        self.assertTrue(Path(state['lastFile']).is_file())
        self.assertTrue(state['sourcesReady'])
        folder = Path(state['sourcesFolder'])
        for filename in ('capture.mkv', 'desktop.flac', 'microphone.flac', 'session.json'):
            self.assertTrue((folder / filename).is_file(), filename)
        command = json.loads((self.home / 'recorder-args.json').read_text())
        self.assertEqual([command[i + 1] for i, value in enumerate(command) if value == '-a'], ['default_output', 'default_input'])
