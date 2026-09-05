"""Device discovery and an OMA-BS-owned GPU Screen Recorder session.

Capture geometry and mpv options follow Omarchy's capture helpers. Children stay
owned by this supervisor; control files survive a Quickshell popup/reload.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid
import audio_sources
import live_stream


def output(command, timeout=8):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-500:] or f'{command[0]} failed')
    return result.stdout


def devices():
    microphones = [{'id': 'default_input', 'label': 'System default microphone'}]
    cameras = []
    warnings = []
    try:
        seen = {'default_input', 'default_output'}
        for line in output(['gpu-screen-recorder', '--list-audio-devices']).splitlines():
            name, separator, label = line.partition('|')
            name = name.strip()
            if not separator or not name or name in seen or name.endswith('.monitor'):
                continue
            seen.add(name)
            microphones.append({'id': name, 'label': label.strip() or name})
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        warnings.append('Microphone list unavailable: ' + str(error))
    try:
        for line in output(['omarchy-capture-webcam-list']).splitlines():
            parts = line.strip().split(None, 1)
            if parts and re.fullmatch(r'/dev/video\d+', parts[0]):
                cameras.append({'id': parts[0], 'label': parts[1] if len(parts) > 1 else parts[0]})
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        warnings.append('Camera list unavailable: ' + str(error))
    return {'ok': True, 'microphones': microphones, 'cameras': cameras, 'warnings': warnings}


def validate_settings(args):
    if args.capture not in {'display', 'window', 'region'}:
        raise RuntimeError('Choose display, window, or region capture')
    if args.audio not in {'none', 'desktop', 'microphone', 'both'}:
        raise RuntimeError('Unknown audio mode')
    if args.fps not in {30, 60} or args.webcam_size not in {'small', 'medium', 'large'}:
        raise RuntimeError('Unsupported frame rate or camera size')
    if args.audio in {'microphone', 'both'} and args.microphone != 'default_input':
        # Membership, not shell escaping: pass only a recorder-advertised input.
        if args.microphone not in {item['id'] for item in devices()['microphones']}:
            raise RuntimeError('Selected microphone is unavailable. Refresh devices and choose again.')
    if args.webcam:
        available = devices()['cameras']
        if not available:
            raise RuntimeError('No capture-capable webcam found. Connect one or turn the overlay off.')
        if not args.camera:
            args.camera = available[0]['id']
        if args.camera not in {item['id'] for item in available}:
            raise RuntimeError('Selected camera is unavailable. Refresh devices and choose again.')


def capture_command(args, target, destination):
    command = ['gpu-screen-recorder', '-w', target, '-k', 'auto', '-f', str(args.fps),
               '-fm', 'cfr', '-fallback-cpu-encoding', 'yes', '-o', str(destination)]
    if getattr(args, 'stream', False):
        command = ['gpu-screen-recorder', '-w', target, '-k', 'h264', '-f', str(args.fps),
                   '-fm', 'cfr', '-fallback-cpu-encoding', 'yes', '-c', 'mpegts',
                   '-bm', 'cbr', '-q', '6000', '-keyint', '2']
    sources = []
    if args.audio in {'desktop', 'both'}:
        sources.append('default_output')
    if args.audio in {'microphone', 'both'}:
        sources.append(args.microphone)
    if sources:
        if getattr(args, 'separate_audio', False):
            for source in sources:
                command += ['-a', source]
        else:
            command += ['-a', '|'.join(sources)]
        command += ['-ac', 'aac']
    return command


def camera_command(args, formats=''):
    capture_options = 'framerate=30'
    for resolution in ('640x360', '1280x720', '1920x1080'):
        if resolution in formats:
            capture_options = 'video_size=' + resolution + ',' + capture_options
            break
    return ['mpv', 'av://v4l2:' + args.camera, '--profile=low-latency', '--untimed',
            '--no-cache', '--demuxer-lavf-o=' + capture_options, '--vf=lavfi=[crop=ih*8/9:ih]',
            '--title=WebcamOverlay', '--wayland-app-id=WebcamOverlay-' + args.webcam_size,
            '--no-border', '--no-audio', '--no-osc', '--osd-level=0', '--msg-level=all=warn']


def region_overlay_geometry(target, size):
    match = re.fullmatch(r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', target)
    if not match:
        return None
    width, height, x, y = map(int, match.groups())
    margin = min(40, width // 10, height // 10)
    scale = min(height, (width - 2 * margin) / 0.3)
    camera_height = max(2, round(scale * {'small': .18, 'medium': .25, 'large': .3375}[size]))
    camera_width = max(2, round(camera_height * 8 / 9))
    return camera_width, camera_height, x + width - camera_width - margin, y + height - camera_height - margin


def wait_camera(camera, stop_file, camera_off):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if stop_file.exists() or camera_off.exists():
            return None
        if camera.poll() is not None:
            raise RuntimeError('Camera failed to open. It may be busy; see capture.log.')
        clients = json.loads(output(['hyprctl', 'clients', '-j'], timeout=2))
        client = next((c for c in clients if c.get('pid') == camera.pid and c.get('title') == 'WebcamOverlay'), None)
        if client:
            return client
        time.sleep(.1)
    raise RuntimeError('Camera window did not appear; check capture.log.')


def place_region_camera(client, target, size):
    geometry = region_overlay_geometry(target, size)
    if geometry is None:
        return
    address = client.get('address', '')
    if not re.fullmatch(r'0x[0-9a-fA-F]+', address):
        raise RuntimeError('Camera window address is invalid')
    width, height, x, y = geometry
    for action, a, b, old_action in [('resize', width, height, 'resizewindowpixel'), ('move', x, y, 'movewindowpixel')]:
        lua = f'hl.dsp.window.{action}({{ window = "address:{address}", x = {a}, y = {b} }})'
        try:
            output(['hyprctl', 'dispatch', lua], timeout=2)
        except RuntimeError:
            output(['hyprctl', 'dispatch', old_action, f'exact {a} {b},address:{address}'], timeout=2)


def control_path(backend, token, action):
    if not re.fullmatch(r'[a-f0-9]{32}', token or '') or action not in {'stop', 'camera-off', 'broadcast-on', 'broadcast-off'}:
        raise RuntimeError('Invalid capture control request')
    return backend.CONFIG_DIR / f'capture-{token}.{action}'


def request(backend, state, action):
    path = control_path(backend, state.get('token'), action)
    path.touch(mode=0o600, exist_ok=True)
    return {'ok': True, 'message': {'stop':'Stopping and saving…', 'camera-off':'Closing webcam…',
                                  'broadcast-on':'Starting destinations…', 'broadcast-off':'Stopping stream; recording continues…'}[action]}


def busy(config_dir):
    path = config_dir / 'capture.lock'
    if not path.exists():
        return False
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def launch(backend, args):
    backend.require('gpu-screen-recorder')
    backend.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with (backend.CONFIG_DIR / 'capture.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('OMA-BS is already recording, choosing a source, or saving')
        if backend.is_recording():
            raise RuntimeError('Another screen recording is active. Stop it in its own app first.')
        validate_settings(args)
        if getattr(args, 'stream', False):
            args.separate_audio = True
            backend.require('ffmpeg')
            live_stream.check_ffmpeg(backend.CONFIG_DIR)
            live_stream.ready_destinations(backend)
        if args.separate_audio:
            backend.require('ffmpeg')
            backend.require('ffprobe')
        if args.webcam:
            backend.require('mpv')
        backend.VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        filename = 'oma-bs-' + time.strftime('%Y%m%d-%H%M%S') + '-' + token[:8] + '.mp4'
        state = {'engine': 'oma-bs', 'token': token, 'phase': 'starting', 'recording': False,
                 'cameraOpen': False, 'startedAt': backend.now(), 'message': 'Opening capture source…',
                 'lastFile': str(backend.VIDEO_DIR / filename), 'capture': args.capture, 'audio': args.audio}
        if args.separate_audio:
            folder = backend.VIDEO_DIR / 'Sources' / Path(filename).stem
            state.update(masterFile=str(folder / 'capture.mkv'), sourcesFolder=str(folder), sourcesReady=False)
        if getattr(args, 'stream', False):
            state.update(streamCapable=True, broadcastEnabled=True, streamState='connecting', destinations=[], lastStreamFailure=[],
                         transportFile=str(folder / 'capture.ts'))
        backend.write_json(backend.STATE_FILE, state)
        saved = backend.config()
        saved.update({'capture': args.capture, 'audio': args.audio, 'microphone': args.microphone,
                      'camera': args.camera, 'webcamSize': args.webcam_size, 'fps': args.fps,
                      'separateAudio': args.separate_audio,
                      'webcam': False})  # Never reopen a camera on shell restart.
        backend.write_json(backend.CONFIG_FILE, saved)
        command = [sys.executable, str(backend.PLUGIN_DIR / 'scripts/oma-bs'), 'run-session',
                   '--token', token, '--lock-fd', str(lock.fileno()),
                   '--capture', args.capture, '--audio', args.audio, '--microphone', args.microphone,
                   '--camera', args.camera, '--webcam-size', args.webcam_size, '--fps', str(args.fps)]
        if args.webcam:
            command.append('--webcam')
        if args.separate_audio:
            command.append('--separate-audio')
        if getattr(args, 'stream', False): command.append('--stream')
        try:
            with (backend.CONFIG_DIR / 'capture.log').open('ab') as log:
                log.write((backend.now() + ' OMA-BS session ' + token + '\n').encode())
                log.flush()
                subprocess.Popen(command, pass_fds=(lock.fileno(),), start_new_session=True,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        except Exception:
            state.update(phase='ended', message='Could not launch capture. See capture.log.')
            backend.write_json(backend.STATE_FILE, state)
            raise
    return {'ok': True, 'message': 'Choose your capture source…', 'state': state}


def close_child(proc, group=False):
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM) if group else proc.terminate()
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            # Only our picker/preview, never a recorder or unrelated app.
            os.killpg(proc.pid, signal.SIGKILL) if group else proc.kill()
            proc.wait()


def run(backend, args):
    state = backend.read_json(backend.STATE_FILE, {})
    if state.get('token') != args.token:
        raise RuntimeError('Capture session has been superseded')
    # The inherited lock excludes double-clicks and other OMA-BS bar instances.
    with (backend.CONFIG_DIR / 'capture.lock').open('a') as expected:
        if os.fstat(args.lock_fd).st_ino != os.fstat(expected.fileno()).st_ino:
            raise RuntimeError('Capture lock does not match')
    stop_file = control_path(backend, args.token, 'stop')
    camera_off = control_path(backend, args.token, 'camera-off')
    broadcast_on = control_path(backend, args.token, 'broadcast-on')
    broadcast_off = control_path(backend, args.token, 'broadcast-off')
    info = backend.process_info(os.getpid())
    state.update(sessionPid=os.getpid(), launcherTicks=info['ticks'] if info else None)
    camera = recorder = picker = None
    broadcast = None
    last_broadcast_status = None
    last_broadcast_poll = 0
    interrupted = False
    def save(**fields):
        state.update(fields)
        backend.write_json(backend.STATE_FILE, state)
    def on_signal(_signum, _frame):
        stop_file.touch(mode=0o600, exist_ok=True)
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    save()
    try:
        target = 'portal'
        if args.capture != 'window':
            command = (['omarchy-hyprland-monitor-focused'] if args.capture == 'display'
                       else ['omarchy-capture-region', 'smart', '--match-monitor'])
            picker = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, start_new_session=True)
            # communicate drains output while allowing a cancelled selection to exit.
            while True:
                if stop_file.exists():
                    close_child(picker, group=True)
                    save(phase='stopped', message='Capture cancelled.', stoppedAt=backend.now())
                    return {'ok': True}
                try:
                    selected, _ = picker.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if picker.returncode or not selected.strip():
                save(phase='stopped', message='Capture selection cancelled.', stoppedAt=backend.now())
                return {'ok': True}
            selected = selected.strip()
            if args.capture == 'display':
                target = selected
            elif selected.startswith('monitor:'):
                target = selected[len('monitor:'):]
            else:
                match = re.fullmatch(r'(-?\d+),(-?\d+)\s+(\d+)x(\d+)', selected)
                if not match:
                    raise RuntimeError('Invalid capture-region response')
                x, y, width, height = match.groups()
                target = f'{width}x{height}+{x}+{y}'
        if stop_file.exists():
            save(phase='stopped', message='Capture cancelled.', stoppedAt=backend.now())
            return {'ok': True}
        formats = ''
        if args.webcam and not camera_off.exists():
            try:
                formats = output(['v4l2-ctl', '--list-formats-ext', '-d', args.camera], timeout=4)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                formats = ''
        if args.webcam and not camera_off.exists() and not stop_file.exists():
            camera = subprocess.Popen(camera_command(args, formats))
            client = wait_camera(camera, stop_file, camera_off)
            if client and args.capture == 'region':
                place_region_camera(client, target, args.webcam_size)
            # Let the mapped overlay settle into its position before encoding.
            until = time.monotonic() + 0.15
            while time.monotonic() < until and not stop_file.exists() and not camera_off.exists():
                time.sleep(0.05)
            if camera.poll() is not None:
                raise RuntimeError('Camera failed to open. It may be busy; see capture.log.')
            if camera_off.exists() or stop_file.exists():
                close_child(camera)
            save(cameraOpen=camera.poll() is None)
        if stop_file.exists():
            save(phase='stopped', message='Capture cancelled.', stoppedAt=backend.now())
            return {'ok': True}
        destination = Path(state.get('transportFile', state.get('masterFile', state['lastFile'])))
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = capture_command(args, target, destination)
        # Retain Omarchy's cap for unusually large displays, keeping GPU load bounded.
        if not re.fullmatch(r'\d+x\d+\+-?\d+\+-?\d+', target):
            monitors = json.loads(output(['hyprctl', 'monitors', '-j']))
            focused = next((m for m in monitors if m.get('focused')), {})
            command += ['-s', '1920x1080' if getattr(args, 'stream', False) else '3840x2160' if focused.get('width', 0) > 3840 or focused.get('height', 0) > 2160 else '0x0']
        elif getattr(args, 'stream', False):
            command += ['-s', '1920x1080']
        print('Capture command:', repr(command), flush=True)
        recorder = subprocess.Popen(command, stdout=subprocess.PIPE if getattr(args, 'stream', False) else None, bufsize=0)
        if getattr(args, 'stream', False):
            initial_destinations = [] if broadcast_off.exists() else live_stream.ready_destinations(backend)
            if broadcast_off.exists():
                broadcast_off.unlink(missing_ok=True)
                save(broadcastEnabled=False, streamState='off')
            broadcast = live_stream.Broadcast(recorder.stdout, destination, backend.CONFIG_DIR, args.audio,
                                              initial_destinations)
        while recorder.poll() is None:
            if broadcast:
                if broadcast.error: raise RuntimeError(broadcast.error)
                if broadcast_off.exists() or stop_file.exists():
                    broadcast.disable()
                    broadcast_off.unlink(missing_ok=True)
                    broadcast_on.unlink(missing_ok=True)
                    if state.get('broadcastEnabled'):
                        save(broadcastEnabled=False, streamState='off', destinations=[])
                elif broadcast_on.exists():
                    broadcast_on.unlink(missing_ok=True)
                    try:
                        broadcast.enable(live_stream.ready_destinations(backend))
                        save(broadcastEnabled=True, streamState='connecting')
                    except Exception:
                        save(broadcastEnabled=False, streamState='failed', message='Could not restart streaming. Check saved destinations.')
                if time.monotonic() - last_broadcast_poll > 1:
                    destinations = broadcast.snapshot()
                    sending = sum(d['state'] == 'sending' for d in destinations)
                    failed = sum(d['state'] == 'failed' for d in destinations)
                    stream_state = ('off' if not state.get('broadcastEnabled') else 'failed' if destinations and failed == len(destinations)
                                    else 'partial' if failed else 'sending' if sending == len(destinations) and sending else 'connecting')
                    snapshot = (destinations, stream_state)
                    if snapshot != last_broadcast_status:
                        save(destinations=destinations, streamState=stream_state)
                        failures = [d for d in destinations if d['state'] == 'failed']
                        if failures:
                            save(lastStreamFailure=failures)
                        last_broadcast_status = snapshot
                    last_broadcast_poll = time.monotonic()
            if camera is not None and state.get('cameraOpen'):
                if camera_off.exists() or camera.poll() is not None:
                    close_child(camera)
                    save(cameraOpen=False)
            if stop_file.exists() and not interrupted:
                interrupted = True
                close_child(camera)
                recorder.send_signal(signal.SIGINT)
                save(phase='stopping', cameraOpen=False, message='Saving recording…')
            elif not interrupted and state['phase'] == 'starting' and destination.exists() and destination.stat().st_size > 0:
                save(phase='recording', recording=True, captureStartedAt=backend.now(), message='Recording active')
            time.sleep(0.1)
        close_child(camera)
        save(phase='finishing', recording=False, cameraOpen=False, broadcastEnabled=False, streamState='off', destinations=[], exitCode=recorder.returncode)
        if broadcast:
            broadcast.finish()
            recorder.stdout.close()
            save(message='Preparing stream backup and source audio…')
            if destination.exists() and destination.stat().st_size:
                live_stream.remux_backup(destination, Path(state['masterFile']))
                destination = Path(state['masterFile'])
        try:
            media_info = backend.inspect_media(str(destination), thumbnail=False)
            valid = media_info['duration'] > 0
        except Exception:
            valid = False
        if args.separate_audio and destination.exists():
            save(sourcesReady=True)
        if args.separate_audio and valid:
            save(message='Preparing separate audio files and mixed playback…')
            try:
                audio_sources.finalize(backend, destination, Path(state['lastFile']), args)
            except Exception as error:
                save(phase='ended', message='Source recording kept in ' + str(destination.parent) + '. ' + str(error),
                     stoppedAt=backend.now())
                backend.notify('OMA-BS', 'Audio preparation failed; multitrack source recording kept.')
                return {'ok': False}
        if interrupted and valid:
            save(phase='stopped', message='Saved ' + Path(state['lastFile']).name + (' + source audio files' if args.separate_audio else ''), stoppedAt=backend.now())
            backend.notify('OMA-BS', 'Recording saved')
        else:
            reason = ('Recording ended outside OMA-BS.' if valid
                      else 'Capture did not produce a playable video; selection may have been cancelled.')
            save(phase='ended', message=reason + ' See capture.log for details.', stoppedAt=backend.now())
            backend.notify('OMA-BS', state['message'])
        return {'ok': valid}
    except Exception as error:
        kept_transport = Path(state.get('transportFile', '/nonexistent'))
        save(phase='ended', recording=False, cameraOpen=False, broadcastEnabled=False, streamState='off', destinations=[],
             sourcesReady=state.get('sourcesReady', False) or (kept_transport.is_file() and kept_transport.stat().st_size > 0),
             message=str(error), stoppedAt=backend.now())
        raise
    finally:
        if broadcast: broadcast.disable()
        close_child(picker, group=True)
        close_child(camera)
        # Never force-kill an encode: SIGINT lets GPU Screen Recorder finalize it.
        if recorder is not None and recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            # If fan-out failed to start, drain stdout so a full pipe cannot prevent exit.
            if getattr(args, 'stream', False) and (broadcast is None or not broadcast.thread.is_alive()):
                recorder.communicate()
            save(phase='stopping', message='Waiting for the recorder to finish saving…')
            recorder.wait()
            save(phase='ended', recording=False, cameraOpen=False, message='Capture interrupted; check the saved file and capture.log.')
        if broadcast:
            try: broadcast.finish()
            except RuntimeError: pass
        if recorder is not None and recorder.stdout: recorder.stdout.close()
        os.close(args.lock_fd)
        stop_file.unlink(missing_ok=True)
        camera_off.unlink(missing_ok=True)
        broadcast_on.unlink(missing_ok=True)
        broadcast_off.unlink(missing_ok=True)
