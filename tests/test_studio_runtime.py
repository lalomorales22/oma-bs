import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import studio_runtime as runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.plugin = self.base / 'plugin'
        self.studio = self.base / 'data/oma-bs/studio'
        (self.plugin / 'studio').mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def dependencies(self, root):
        modules = root / 'node_modules'
        (modules / '.bin').mkdir(parents=True)
        (modules / 'vite').mkdir()
        (modules / 'vite/bin.js').write_text('dependency fixture')
        (modules / '.bin/vite').symlink_to('../vite/bin.js')
        return modules

    def test_migration_keeps_working_relative_symlink_outside_plugin(self):
        old = self.dependencies(self.plugin / 'studio')
        moves = []
        runtime.migrate_dependencies(self.plugin, self.studio, moves)
        self.assertFalse(old.exists())
        self.assertTrue((self.studio / 'node_modules/.bin/vite').is_symlink())
        self.assertEqual((self.studio / 'node_modules/.bin/vite').read_text(), 'dependency fixture')
        self.assertFalse(any(p.is_symlink() for p in self.plugin.rglob('*')))

    def test_existing_runtime_dependencies_preserved_and_moves_reversible(self):
        old = self.dependencies(self.plugin / 'studio')
        existing = self.dependencies(self.studio)
        (existing / 'vite/bin.js').write_text('existing runtime')
        moves = []
        runtime.migrate_dependencies(self.plugin, self.studio, moves)
        self.assertEqual(len(moves), 2)
        self.assertEqual((moves[0][1] / 'vite/bin.js').read_text(), 'existing runtime')
        runtime.restore_moves(moves)
        self.assertEqual((old / '.bin/vite').read_text(), 'dependency fixture')
        self.assertEqual((existing / '.bin/vite').read_text(), 'existing runtime')

    def test_source_sync_does_not_copy_npm_tree_back(self):
        self.dependencies(self.plugin / 'studio')
        (self.plugin / 'studio/index.html').write_text('<title>OMA-BS</title>')
        runtime.sync_source(self.plugin, self.studio)
        self.assertTrue((self.studio / 'index.html').is_file())
        self.assertFalse((self.studio / 'node_modules').exists())

    def test_reject_runtime_inside_plugin(self):
        with mock.patch.dict(os.environ, {'XDG_DATA_HOME': str(self.plugin)}):
            with self.assertRaisesRegex(RuntimeError, 'outside'):
                runtime.runtime_path(self.plugin)

    def test_lockfile_change_refreshes_existing_browser_dependencies(self):
        self.studio.mkdir(parents=True)
        lock = self.studio / 'package-lock.json'
        lock.write_text('{"version":1}')
        vite = self.studio / 'node_modules/vite/bin/vite.js'
        vite.parent.mkdir(parents=True); vite.write_text('fixture')
        with mock.patch.object(runtime.shutil, 'which', return_value='/usr/bin/npm'), mock.patch.object(runtime.subprocess, 'run', return_value=subprocess.CompletedProcess(['npm'], 0)) as install:
            runtime.ensure_dependencies(self.studio, subprocess.DEVNULL)
            self.assertEqual(install.call_count, 1)
            runtime.ensure_dependencies(self.studio, subprocess.DEVNULL)
            self.assertEqual(install.call_count, 1)
            lock.write_text('{"version":2}')
            runtime.ensure_dependencies(self.studio, subprocess.DEVNULL)
            self.assertEqual(install.call_count, 2)
            lock.write_text('{"version":3}')
            install.return_value = subprocess.CompletedProcess(['npm'], 1)
            with self.assertRaises(RuntimeError): runtime.ensure_dependencies(self.studio, subprocess.DEVNULL)
            self.assertFalse(runtime.dependencies_current(self.studio))

    def test_real_omarchy_validator_before_and_after(self):
        validator = ROOT.parent / 'omarchy-upstream/bin/omarchy-plugin-validate'
        if not validator.exists():
            self.skipTest('Omarchy upstream validator not present in this checkout')
        (self.plugin / 'manifest.json').write_text((ROOT / 'manifest.json').read_text())
        (self.plugin / 'BarWidget.qml').write_text((ROOT / 'BarWidget.qml').read_text())
        self.dependencies(self.plugin / 'studio')
        before = subprocess.run([str(validator), str(self.plugin)], capture_output=True, text=True)
        self.assertNotEqual(before.returncode, 0)
        self.assertIn('symlink', before.stderr)
        runtime.migrate_dependencies(self.plugin, self.studio, [])
        after = subprocess.run([str(validator), str(self.plugin)], capture_output=True, text=True)
        self.assertEqual(after.returncode, 0, after.stderr)

    def test_complete_updater_migrates_and_enables(self):
        self.run_updater(False)

    def test_failed_validation_restores_files_and_dependency_locations(self):
        self.run_updater(True)

    def run_updater(self, fail_validation):
        loader = importlib.machinery.SourceFileLoader('oma_update_test', str(ROOT / 'scripts/update-local'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        update = importlib.util.module_from_spec(spec)
        loader.exec_module(update)
        source = self.base / 'release'
        for rel in update.FILES:
            incoming = source / rel
            incoming.parent.mkdir(parents=True, exist_ok=True)
            incoming.write_text('new ' + rel)
            previous = self.plugin / rel
            previous.parent.mkdir(parents=True, exist_ok=True)
            if rel not in ('NativeGallery.qml', 'VideoPreview.qml', 'scripts/capture_session.py', 'scripts/audio_sources.py', 'scripts/scene_editor.py', 'MediaDock.qml', 'EditorPane.qml', 'EditorField.qml'):
                previous.write_text('old ' + rel)
        manifest = json.dumps({'id': 'lalo.oma-bs'})
        (self.plugin / 'manifest.json').write_text(manifest)
        old = self.dependencies(self.plugin / 'studio')
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if args[0] == 'pgrep':
                return subprocess.CompletedProcess(args, 1)
            if args[:3] == ['omarchy', 'plugin', 'validate'] and args[3] == str(self.plugin):
                self.assertFalse(old.exists(), 'Must migrate BEFORE target validation')
                if fail_validation:
                    raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 0)
        with mock.patch.object(update, 'SOURCE', source), mock.patch.object(update, 'TARGET', self.plugin), mock.patch.object(update, 'runtime_path', return_value=self.studio), mock.patch.object(update, 'stop_studio_servers'), mock.patch.object(update.Path, 'home', return_value=self.base / 'home'), mock.patch.object(update.subprocess, 'run', side_effect=run):
            if fail_validation:
                with self.assertRaises(subprocess.CalledProcessError):
                    update.main()
            else:
                update.main()
        self.assertEqual((self.plugin / 'BarWidget.qml').read_text(), ('old ' if fail_validation else 'new ') + 'BarWidget.qml')
        self.assertEqual(old.exists(), fail_validation)
        self.assertEqual((self.plugin / 'NativeGallery.qml').exists(), not fail_validation)
        self.assertEqual((self.plugin / 'VideoPreview.qml').exists(), not fail_validation)
        self.assertEqual((self.plugin / 'scripts/capture_session.py').exists(), not fail_validation)
        self.assertEqual((self.plugin / 'scripts/audio_sources.py').exists(), not fail_validation)
        for rel in ('scripts/scene_editor.py', 'MediaDock.qml', 'EditorPane.qml', 'EditorField.qml'):
            self.assertEqual((self.plugin / rel).exists(), not fail_validation)
        self.assertEqual(['omarchy', 'plugin', 'enable', 'lalo.oma-bs'] in calls, not fail_validation)


if __name__ == '__main__':
    unittest.main()
