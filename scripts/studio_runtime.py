#!/usr/bin/env python3
"""Keep the writable studio and npm dependencies outside Omarchy's plugin tree."""
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

EXCLUDED = {'node_modules', 'dist', '.git', '.vite', '__pycache__'}


def dependency_digest(runtime):
    return hashlib.sha256((runtime / 'package-lock.json').read_bytes()).hexdigest()


def dependencies_current(runtime):
    marker = runtime / '.oma-bs-lock.sha256'
    return ((runtime / 'node_modules/vite/bin/vite.js').is_file() and marker.is_file()
            and marker.read_text().strip() == dependency_digest(runtime))


def ensure_dependencies(runtime, log):
    if dependencies_current(runtime):
        return
    if not shutil.which('npm'):
        raise RuntimeError('Node.js/npm is required to prepare OMA-BS Studio')
    digest = dependency_digest(runtime)
    result = subprocess.run(['npm', 'ci'], cwd=runtime, stdout=log, stderr=log)
    if result.returncode:
        raise RuntimeError('Studio dependency setup failed. See the OMA-BS studio.log.')
    (runtime / '.oma-bs-lock.sha256').write_text(digest + '\n')


def runtime_path(plugin):
    data_home = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    if not data_home.is_absolute():
        raise RuntimeError('XDG_DATA_HOME must be absolute')
    runtime = (data_home / 'oma-bs/studio').resolve()
    plugin = plugin.resolve()
    if runtime == plugin or plugin in runtime.parents:
        raise RuntimeError('Studio runtime must be outside the plugin directory')
    return runtime


def migrate_dependencies(plugin, runtime, moves):
    old = plugin / 'studio/node_modules'
    if not old.exists() and not old.is_symlink():
        return
    if old.is_symlink() or not old.is_dir():
        raise RuntimeError('Expected studio/node_modules to be a directory')
    runtime.mkdir(parents=True, exist_ok=True)
    destination = runtime / 'node_modules'
    if destination.is_symlink():
        raise RuntimeError('Refusing to replace a runtime node_modules symlink')
    if destination.exists():
        backup_root = runtime.parent / 'dependency-backups'
        backup_root.mkdir(parents=True, exist_ok=True)
        saved = Path(tempfile.mkdtemp(prefix='before-migration-', dir=backup_root)) / 'node_modules'
        shutil.move(str(destination), str(saved))
        moves.append((destination, saved))
    shutil.move(str(old), str(destination))
    moves.append((old, destination))


def restore_moves(moves):
    for original, relocated in reversed(moves):
        if relocated.exists() and not original.exists():
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(relocated), str(original))


def sync_source(plugin, runtime):
    source = plugin / 'studio'
    runtime.mkdir(parents=True, exist_ok=True)
    for folder, directories, files in os.walk(source):
        directories[:] = [name for name in directories if name not in EXCLUDED]
        for name in directories + files:
            if (Path(folder) / name).is_symlink():
                raise RuntimeError('Unexpected studio source symlink: ' + str(Path(folder) / name))
    shutil.copytree(source, runtime, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*EXCLUDED))


def server_info(pid, roots):
    """Only same-user Vite node processes with this app's exact cwd and script."""
    try:
        proc = Path('/proc') / str(pid)
        if proc.stat().st_uid != os.getuid():
            return None
        args = (proc / 'cmdline').read_bytes().decode(errors='replace').rstrip('\0').split('\0')
        if not args or Path(args[0]).name not in {'node', 'nodejs'}:
            return None
        cwd = (proc / 'cwd').resolve()
        candidates = set()
        for root in roots:
            root = root.resolve()
            if cwd == root:
                candidates.update([str(root / 'node_modules/.bin/vite'), str(root / 'node_modules/vite/bin/vite.js')])
        if not any(arg in candidates for arg in args[1:]):
            return None
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else {'pid': pid, 'ticks': fields[19]}
    except (OSError, ValueError, IndexError):
        return None


def studio_servers(roots):
    result = []
    for proc in Path('/proc').iterdir():
        if proc.name.isdigit():
            info = server_info(int(proc.name), roots)
            if info:
                result.append(info)
    return result


def stop_studio_servers(roots):
    targets = studio_servers(roots)
    for target in targets:
        try:
            fd = os.pidfd_open(target['pid'])
            try:
                if server_info(target['pid'], roots) == target:
                    signal.pidfd_send_signal(fd, signal.SIGTERM)
            finally:
                os.close(fd)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not any(server_info(t['pid'], roots) == t for t in targets):
            return
        time.sleep(0.1)
    raise RuntimeError('Studio server has not exited; close it before updating. No force-kill performed.')


def ready():
    try:
        with urllib.request.urlopen('http://127.0.0.1:4173/', timeout=1) as response:
            return b'<title>OMA-BS</title>' in response.read(16384)
    except OSError:
        return False


def launch(plugin):
    runtime = runtime_path(plugin)
    runtime.mkdir(parents=True, exist_ok=True)
    with (runtime.parent / 'studio-launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop_studio_servers([plugin / 'studio'])
        migrate_dependencies(plugin, runtime, [])
        sync_source(plugin, runtime)
        if not (dependencies_current(runtime) and studio_servers([runtime]) and ready()):
            stop_studio_servers([runtime])
            log_path = runtime.parent / 'studio.log'
            with log_path.open('ab') as log:
                ensure_dependencies(runtime, log)
                node = shutil.which('node')
                if not node:
                    raise RuntimeError('Node.js is required for OMA-BS Studio')
                env = dict(os.environ)
                env['OMA_BS_STREAM_SETTINGS'] = str(Path(os.environ.get('OMA_BS_CONFIG_DIR', Path.home() / '.config/oma-bs')) / 'streaming.json')
                proc = subprocess.Popen([node, str(runtime / 'node_modules/vite/bin/vite.js'),
                                         '--host', '127.0.0.1', '--port', '4173', '--strictPort'],
                                        cwd=runtime, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                        start_new_session=True)
                for _ in range(80):
                    if proc.poll() is not None:
                        raise RuntimeError('Studio server exited. See ' + str(log_path))
                    if ready():
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError('Studio is not ready yet. See ' + str(log_path))
    browser = shutil.which('omarchy-launch-browser') or shutil.which('xdg-open')
    if not browser:
        raise RuntimeError('Open http://127.0.0.1:4173/ in your browser')
    subprocess.Popen([browser, 'http://127.0.0.1:4173/'], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    try:
        launch(Path(__file__).resolve().parent.parent)
    except Exception as error:
        print('OMA-BS: ' + str(error), file=sys.stderr)
        notify = shutil.which('omarchy-notification-send') or shutil.which('notify-send')
        if notify:
            subprocess.run([notify, 'OMA-BS Studio', str(error)])
        raise SystemExit(1)
