"""Small, non-destructive native composition engine. No shell interpolation."""
import math
import os
from pathlib import Path
import signal
import subprocess
import uuid

SIZES = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080), '19:6': (1900, 600)}
DRAFTS = {'16:9': (480, 270), '9:16': (270, 480), '1:1': (270, 270), '19:6': (570, 180)}


def number(value, label, low, high):
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise RuntimeError(label + ' must be a number') from None
    if not math.isfinite(result) or not low <= result <= high:
        raise RuntimeError(f'{label} must be between {low:g} and {high:g}')
    return result


def validate(backend, project):
    if not isinstance(project, dict) or project.get('version') != 1:
        raise RuntimeError('Unsupported edit project')
    ratio = project.get('ratio')
    if ratio not in SIZES:
        raise RuntimeError('Choose a supported canvas shape')
    duration = number(project.get('duration'), 'Duration', 0.1, 21600)
    layers = project.get('layers', [])
    if not isinstance(layers, list) or len(layers) > 8:
        raise RuntimeError('Use up to eight layers per edit')
    tracks = []
    for index, raw in enumerate([project.get('base')] + layers):
        if not isinstance(raw, dict) or not isinstance(raw.get('path'), str):
            raise RuntimeError('Choose a media file for every track')
        info = backend.inspect_media(raw['path'], thumbnail=False)
        if index == 0 and info['kind'] == 'audio':
            raise RuntimeError('Choose an image or video as the base')
        track = dict(info)
        track['mediaIn'] = number(raw.get('mediaIn', 0), 'Source start', 0, 21600)
        track['at'] = 0 if index == 0 else number(raw.get('at', 0), 'Timeline start', 0, duration - 0.01)
        track['volume'] = number(raw.get('volume', 1), 'Volume', 0, 2)
        if info['kind'] != 'image':
            remaining = info['duration'] - track['mediaIn']
            if remaining < 0.05 or (index == 0 and duration > remaining + 0.05):
                raise RuntimeError('The selected range extends past the source media')
            track['length'] = min(duration - track['at'], remaining)
        else:
            track['length'] = duration - track['at']
        # A layer can end early without changing the original file.
        if index and raw.get('length') is not None:
            track['length'] = number(raw['length'], 'Layer duration', 0.05, track['length'] + 0.001)
        if info['kind'] != 'audio':
            track['fit'] = raw.get('fit', 'crop')
            if track['fit'] not in ('crop', 'fit'):
                raise RuntimeError('Choose crop or fit')
            for key in ('panX', 'panY'):
                track[key] = number(raw.get(key, 0.5), key, 0, 1)
            for key, default in [('x', 0.65), ('y', 0.65), ('w', 0.3), ('h', 0.3)]:
                track[key] = number(raw.get(key, default), key, 0.02 if key in ('w', 'h') else 0, 1)
            if index and (track['x'] + track['w'] > 1.001 or track['y'] + track['h'] > 1.001):
                raise RuntimeError('Keep the layer inside the canvas')
        tracks.append(track)
    return ratio, duration, tracks


def render(backend, project, draft=False):
    backend.require('ffmpeg')
    ratio, duration, tracks = validate(backend, project)
    width, height = (DRAFTS if draft else SIZES)[ratio]
    folder = backend.VIDEO_DIR / 'Exports'
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / (('Preview' if draft else 'OMA-BS-edit') + '-' + uuid.uuid4().hex[:12] + '.mp4')
    temporary = folder / ('.' + output.stem + '.partial.mp4')
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-n', '-filter_complex_threads', '1']
    for track in tracks:
        if track['kind'] == 'image':
            command += ['-loop', '1', '-framerate', '30']
        command += backend.LOCAL_INPUT_OPTIONS + ['-i', track['path']]
    filters, audio_labels = [], []
    canvas = 'v0'
    for index, track in enumerate(tracks):
        length, start, at = track['length'], track['mediaIn'], track['at']
        if track['kind'] != 'audio':
            w = width if index == 0 else max(2, round(width * track['w'] / 2) * 2)
            h = height if index == 0 else max(2, round(height * track['h'] / 2) * 2)
            vf = f'[{index}:v:0]trim=start={start}:duration={length},setpts=PTS-STARTPTS,fps=30,setsar=1,'
            if track['fit'] == 'crop':
                vf += f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}:(iw-ow)*{track['panX']}:(ih-oh)*{track['panY']},format=rgba"
            else:
                vf += f'scale={w}:{h}:force_original_aspect_ratio=decrease,format=rgba,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=' + ('black' if index == 0 else 'black@0')
            vf += f',setpts=PTS+{at}/TB[v{index}]'
            filters.append(vf)
            if index:
                next_canvas = f'c{index}'
                filters.append(f"[{canvas}][v{index}]overlay=x={round(width * track['x'])}:y={round(height * track['y'])}:eof_action=pass:repeatlast=0:enable='between(t,{at},{at + length})'[{next_canvas}]")
                canvas = next_canvas
        if track['hasAudio'] and track['volume'] > 0:
            label = f'a{index}'
            filters.append(f"[{index}:a:0]atrim=start={start}:duration={length},asetpts=PTS-STARTPTS,aresample=48000,volume={track['volume']},adelay={round(at * 1000)}:all=1[{label}]")
            audio_labels.append(f'[{label}]')
    if audio_labels:
        filters.append(''.join(audio_labels) + f'amix=inputs={len(audio_labels)}:normalize=0:duration=longest,alimiter=limit=0.95:latency=1,apad[aout]')
    command += ['-filter_complex', ';'.join(filters), '-map', f'[{canvas}]']
    if audio_labels:
        command += ['-map', '[aout]', '-c:a', 'aac', '-b:a', '192k']
    command += ['-t', str(duration), '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '24' if draft else '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)]
    proc = None
    previous = signal.getsignal(signal.SIGTERM)

    def interrupted(_signum, _frame):
        if proc and proc.poll() is None:
            proc.terminate()
        raise RuntimeError('Render interrupted; source files are unchanged')

    signal.signal(signal.SIGTERM, interrupted)
    try:
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        _, error = proc.communicate(timeout=7200)
        if proc.returncode:
            raise RuntimeError('Render failed: ' + error.decode(errors='replace')[-800:])
        info = backend.inspect_media(str(temporary), thumbnail=False)
        if abs(info['duration'] - duration) > 0.2:
            raise RuntimeError('Render was incomplete; source files are unchanged')
        os.link(temporary, output)  # Atomic publication that cannot overwrite a file.
        return {'ok': True, 'path': str(output), 'uri': output.as_uri(), 'name': output.name, 'kind': 'video', 'draft': draft}
    finally:
        signal.signal(signal.SIGTERM, previous)
        if proc and proc.poll() is None:
            proc.kill()
            proc.communicate()
        temporary.unlink(missing_ok=True)
