#!/usr/bin/env python3
"""Private RTMP(S) transport shared by the native and browser recorders.

FFmpeg handles local audio conversion only. A small native worker passes
connection options directly to libavformat, bypassing CLI preset routing.
"""
import errno
import ctypes.util
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import shlex
import stat
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlsplit


def connection_options(destination):
    url, key = destination['url'], destination['key']
    if not isinstance(url, str) or not isinstance(key, str):
        raise ValueError('Invalid destination')
    if not key or max(len(url), len(key)) > 900 or any(ord(c) < 32 or ord(c) == 127 for c in url + key):
        raise ValueError('Invalid destination')
    parsed = urlsplit(url)
    if parsed.scheme not in ('rtmp', 'rtmps') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Invalid destination')
    host = '[' + parsed.hostname + ']' if ':' in parsed.hostname else parsed.hostname
    endpoint = parsed.scheme + '://' + host + (':' + str(parsed.port) if parsed.port else '')
    options = {'rtmp_app': parsed.path.strip('/') + ('?' + parsed.query if parsed.query else ''),
               'rtmp_playpath': key, 'rtmp_tcurl': url.rstrip('/'),
               'rw_timeout': '8000000'}
    if parsed.scheme == 'rtmps':
        options['tls_verify'] = '1'
    return endpoint, options


def read_destination(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 65536:
            raise ValueError('Invalid private destination file')
        destination = json.load(handle)
    connection_options(destination)
    return destination


def conversion_command(audio_mode):
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-v', 'error',
               '-protocol_whitelist', 'pipe', '-f', 'mpegts', '-i', 'pipe:0']
    if audio_mode == 'none':
        command += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-map', '0:v:0', '-map', '1:a:0', '-shortest']
    elif audio_mode == 'both':
        command += ['-filter_complex', '[0:a:0][0:a:1]amix=inputs=2:normalize=1:duration=longest[a]', '-map', '0:v:0', '-map', '[a]']
    elif audio_mode == 'ready':
        return command + ['-map', '0:v:0', '-map', '0:a?', '-c', 'copy',
                          '-flush_packets', '1', '-f', 'flv', 'pipe:1']
    else:
        command += ['-map', '0:v:0', '-map', '0:a:0']
    return command + ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000',
                      '-flush_packets', '1', '-f', 'flv', 'pipe:1']


def safe_error(error):
    # Never print an exception or libavformat log: either may contain the key.
    message = str(error).lower()
    for fragments, result in [
        (('unauthorized', 'authentication', 'forbidden', 'badname', 'badauth'), 'Authentication failed'),
        (('certificate',), 'Certificate verify failed'),
        (('connection refused',), 'Connection refused'),
        (('timed out', 'timeout'), 'Connection timed out'),
        (('name or service not known', 'resolve hostname'), 'Failed to resolve hostname'),
        (('invalid data',), 'Invalid data found when processing input'),
    ]:
        if any(fragment in message for fragment in fragments):
            return result
    code = abs(getattr(error, 'errno', 0) or 0)
    return {errno.ECONNREFUSED: 'Connection refused', errno.ETIMEDOUT: 'Connection timed out'}.get(code, 'Input/output error')


def ensure_transport():
    source = Path(__file__).with_suffix('.c')
    flags = shlex.split(os.environ.get('OMA_BS_TRANSPORT_CFLAGS', ''))
    libs = shlex.split(os.environ.get('OMA_BS_TRANSPORT_LIBS', '-lavformat -lavutil'))
    identity = source.read_bytes() + repr((flags, libs, ctypes.util.find_library('avformat'), ctypes.util.find_library('avutil'))).encode()
    digest = hashlib.sha256(identity).hexdigest()[:20]
    cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'oma-bs/transport'
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    binary = cache / ('sender-' + digest)
    with (cache / 'build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not binary.is_file():
            with tempfile.TemporaryDirectory(prefix='build-', dir=cache) as directory:
                temporary = Path(directory) / 'sender'
                command = ['cc', '-O2', '-Wall', '-Wextra', '-Werror', '-D_FORTIFY_SOURCE=2',
                           '-fstack-protector-strong', *flags, str(source), '-o', str(temporary), *libs]
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                if result.returncode:
                    raise RuntimeError('Transport build failed. Install gcc and FFmpeg development headers; on Arch: sudo pacman -S --needed gcc ffmpeg')
                temporary.chmod(0o700)
                temporary.replace(binary)
    return binary


def main():
    converter, sender, reader = None, None, None
    errors = bytearray()
    def stop(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        binary = ensure_transport()
        if sys.argv[1:] == ['--check']:
            print('OMA-BS private streaming transport ready')
            return 0
        destination = read_destination(sys.argv[1])
        audio_mode = sys.argv[2]
        if audio_mode not in ('none', 'both', 'desktop', 'mic', 'ready'):
            raise ValueError('Invalid audio mode')
        environment = dict(os.environ)
        environment.pop('FFREPORT', None)
        converter = subprocess.Popen(conversion_command(audio_mode), stdin=sys.stdin.buffer,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        def drain():
            while True:
                data = converter.stderr.read(4096)
                if not data:
                    break
                errors.extend(data)
                del errors[:-8192]
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        endpoint, options = connection_options(destination)
        read_fd, write_fd = os.pipe()
        try:
            sender = subprocess.Popen([str(binary), str(read_fd)], pass_fds=(read_fd,),
                                      stdin=converter.stdout, env=environment)
            converter.stdout.close()
            with os.fdopen(write_fd, 'w') as credentials:
                write_fd = None
                credentials.write('\n'.join([endpoint, options['rtmp_app'], options['rtmp_playpath'], options['rtmp_tcurl']]) + '\n')
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)
        if sender.wait():
            return 1
        if converter.wait(timeout=5):
            raise RuntimeError('Invalid data found when processing input')
        return 0
    except Exception as error:
        message = ('Transport unavailable. Install gcc and FFmpeg development headers; on Arch: sudo pacman -S --needed gcc ffmpeg'
                   if sys.argv[1:] == ['--check'] else safe_error(error))
        print(message, file=sys.stderr, flush=True)
        return 1
    finally:
        if sender is not None and sender.poll() is None:
            sender.terminate()
            try:
                sender.wait(timeout=.3)
            except subprocess.TimeoutExpired:
                sender.kill()
                sender.wait()
        if converter is not None:
            if converter.poll() is None:
                converter.terminate()
                try:
                    converter.wait(timeout=.3)
                except subprocess.TimeoutExpired:
                    converter.kill()
                    converter.wait()
            if reader:
                reader.join(timeout=.5)
            converter.stdout.close()
            converter.stderr.close()


if __name__ == '__main__':
    raise SystemExit(main())
