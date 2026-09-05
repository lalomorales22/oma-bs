"""Prepare independent audio files and a mixed preview from one capture clock."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def roles(mode):
    return (["desktop"] if mode in {"desktop", "both"} else []) + (["microphone"] if mode in {"microphone", "both"} else [])


def seconds(value, fallback=0):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else fallback
    except (TypeError, ValueError):
        return fallback


def finalize(backend, master, preview, args):
    """Never alter the master. Publish generated outputs only after validation."""
    master, preview = Path(master), Path(preview)
    manifest_path = master.parent / 'session.json'
    manifest = {'schemaVersion': 1, 'status': 'preparing', 'master': master.name,
                'preview': str(preview), 'capture': args.capture, 'audio': args.audio,
                'microphone': args.microphone, 'cameraOverlayRequested': args.webcam,
                'audioFiles': [], 'createdAt': backend.now()}
    backend.write_json(manifest_path, manifest)
    staging = None
    try:
        if preview.exists():
            raise RuntimeError('Preview already exists; refusing to overwrite it')
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                                 '-of', 'json', str(master)], capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RuntimeError('Cannot read the multitrack source recording')
        info = json.loads(result.stdout)
        streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'audio']
        expected = roles(args.audio)
        if len(streams) != len(expected):
            raise RuntimeError(f'Expected {len(expected)} separate audio tracks, found {len(streams)}; source kept')
        origin = seconds(info.get('format', {}).get('start_time'))
        manifest['masterStartSeconds'] = origin
        manifest['audioAlignment'] = '48 kHz; padded to the master timeline start, with timestamp gaps resampled'
        staging = Path(tempfile.mkdtemp(prefix='.preparing-', dir=master.parent))
        staged_preview = staging / 'preview.mp4'
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                   '-copyts', '-start_at_zero', '-i', str(master)]
        filters = [f'[0:a:{index}]aresample=48000:async=1:first_pts=0,asplit=2[stem{index}][mix{index}]'
                   for index in range(len(expected))]
        if len(expected) > 1:
            filters.append(''.join(f'[mix{i}]' for i in range(len(expected)))
                           + f'amix=inputs={len(expected)}:duration=longest:normalize=1[mixed]')
        if filters:
            command += ['-filter_complex', ';'.join(filters)]
        command += ['-map', '0:v:0', '-c:v', 'copy']
        if expected:
            command += ['-map', '[mixed]' if len(expected) > 1 else '[mix0]', '-c:a', 'aac', '-b:a', '192k']
        else:
            command += ['-an']
        command += ['-movflags', '+faststart', str(staged_preview)]
        for index, role in enumerate(expected):
            command += ['-map', f'[stem{index}]', '-vn', '-c:a', 'flac', str(staging / (role + '.flac'))]
            manifest['audioFiles'].append({'role': role, 'file': role + '.flac', 'masterAudioIndex': index,
                                           'originalStartSeconds': seconds(streams[index].get('start_time'), origin) - origin})
        # Camera and recorder have already closed. Only this post-processing job runs.
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if result.returncode:
            raise RuntimeError('Preparing audio failed: ' + result.stderr[-500:])
        if backend.inspect_media(str(staged_preview), thumbnail=False)['duration'] <= 0:
            raise RuntimeError('The mixed preview is empty')
        for entry in manifest['audioFiles']:
            track = staging / entry['file']
            if not track.is_file() or track.stat().st_size == 0:
                raise RuntimeError('An audio file is empty; multitrack source kept')
        for entry in manifest['audioFiles']:
            destination = master.parent / entry['file']
            if destination.exists():
                raise RuntimeError('An audio file already exists; refusing to overwrite it')
        for entry in manifest['audioFiles']:
            os.link(staging / entry['file'], master.parent / entry['file'])
        os.link(staged_preview, preview)  # Atomic no-clobber publication on this filesystem.
        manifest.update(status='ready', finishedAt=backend.now())
        backend.write_json(manifest_path, manifest)
        return manifest
    except Exception as error:
        manifest.update(status='failed', error=str(error))
        backend.write_json(manifest_path, manifest)
        raise
    finally:
        if staging is not None:
            shutil.rmtree(staging)  # Only this invocation's generated scratch outputs.
