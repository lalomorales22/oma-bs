import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

from test_backend import load_backend


class StreamSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.backend = load_backend(self.home)
        self.module = self.backend.stream_settings
        self.data = {'version': 1, 'destinations': [
            {'id': 'channel-one', 'platform': 'twitch', 'url': 'rtmps://ingest.example.test:443/app', 'key': 'example-secret', 'enabled': True},
            {'id': 'channel-two', 'platform': 'tiktok', 'url': '', 'key': '', 'enabled': False},
        ]}

    def save(self, data):
        return self.module.save(self.backend, io.StringIO(json.dumps(data) + '\n'))

    def test_private_round_trip_keeps_incomplete_and_disabled_destinations(self):
        result = self.save(self.data)
        self.assertNotIn('example-secret', json.dumps(result))
        loaded = self.module.load(self.backend)
        self.assertEqual(loaded['destinations'], self.data['destinations'])
        path = self.module.path_for(self.backend)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertNotIn('example-secret', json.dumps(self.backend.config()))
        self.save({'version': 1, 'destinations': []})
        self.assertEqual(self.module.load(self.backend)['destinations'], [])

    def test_invalid_addresses_and_muxer_delimiters_do_not_replace_saved_keys(self):
        self.save(self.data)
        original = self.module.path_for(self.backend).read_bytes()
        cases = [('url', 'https://example.test/live'), ('url', 'rtmps://user:pass@example.test/app'),
                 ('url', 'rtmps://example.test:bad/app'), ('url', 'rtmps://example.test/app|other'),
                 ('key', 'SECRET\nINJECTED'), ('key', 'SECRET[f=flv]'), ('key', 'SECRET\\escape'),
                 ('key', 'x' * 901), ('url', 'rtmps://example.test/' + 'x' * 900)]
        for field, value in cases:
            data = json.loads(json.dumps(self.data))
            data['destinations'][0][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError) as error:
                self.save(data)
            self.assertNotIn(value, str(error.exception))
            self.assertEqual(self.module.path_for(self.backend).read_bytes(), original)

    def test_stdin_cli_does_not_return_or_log_keys(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/oma-bs'
        env = {**os.environ, 'OMA_BS_HOME': str(self.home), 'OMA_BS_CONFIG_DIR': str(self.home / '.config/oma-bs')}
        result = subprocess.run([str(script), 'stream-save'], input=json.dumps(self.data) + '\n', text=True, capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('example-secret', result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['count'], 2)

    def test_oversized_and_duplicate_data_rejected(self):
        with self.assertRaises(RuntimeError):
            self.module.save(self.backend, io.StringIO('x' * 65537))
        self.data['destinations'].append(self.data['destinations'][0])
        with self.assertRaisesRegex(RuntimeError, 'duplicate'):
            self.save(self.data)

    def test_linked_settings_file_is_not_followed(self):
        external = self.home / 'keep.json'
        external.write_text('keep')
        target = self.module.path_for(self.backend)
        target.parent.mkdir(parents=True)
        target.symlink_to(external)
        with self.assertRaises(RuntimeError):
            self.save(self.data)
        with self.assertRaises(RuntimeError):
            self.module.load(self.backend)
        self.assertEqual(external.read_text(), 'keep')

    def test_enable_save_and_stream_read_agree_without_changing_other_channels(self):
        destination = self.data['destinations'][0]
        destination['enabled'] = False
        result = self.save(self.data)
        self.assertEqual((result['enabledCount'], result['readyCount']), (0, 0))
        with self.assertRaisesRegex(RuntimeError, 'saved destinations are disabled'):
            self.backend.live_stream.ready_destinations(self.backend)
        for _ in range(2):
            destination['enabled'] = True
            result = self.save(self.data)
            self.assertEqual((result['enabledCount'], result['readyCount']), (1, 1))
            self.assertEqual(self.backend.live_stream.ready_destinations(self.backend), [destination])
            self.assertFalse(self.module.load(self.backend)['destinations'][1]['enabled'])
            self.assertNotIn('example-secret', json.dumps(result))
        destination['enabled'] = False
        self.assertEqual(self.save(self.data)['readyCount'], 0)

    def test_save_distinguishes_incomplete_enabled_destination(self):
        self.data['destinations'][0]['key'] = ''
        result = self.save(self.data)
        self.assertEqual((result['enabledCount'], result['readyCount']), (1, 0))
        with self.assertRaisesRegex(RuntimeError, 'server URL and stream key'):
            self.backend.live_stream.ready_destinations(self.backend)

    def test_save_does_not_confirm_success_if_disk_does_not_match(self):
        self.save(self.data)
        self.data['destinations'][0]['enabled'] = False
        with mock.patch.object(self.backend, 'write_json'):
            with self.assertRaisesRegex(RuntimeError, 'before verification'):
                self.save(self.data)
