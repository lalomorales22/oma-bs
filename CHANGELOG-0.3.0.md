# OMA-BS 0.3.0 — choose your inputs

## In the dropdown

- **Inputs & camera** shows the available microphones and capture-capable webcams.
- Added microphone-only audio alongside silent, desktop, and both.
- Choose camera size and 30 or 60 fps. Last-used choices are remembered.
- The camera stays off after a shell reload until enabled for a new take.
- A selected device that has disappeared produces an error instead of a silent
  switch to another device. **Refresh devices** picks up newly connected hardware.
- Cancel a pending capture selection directly from the recording button.
- Closing the webcam during capture leaves the screen recording running.
- Capture messages wrap so failure details remain readable.

## Capture lifecycle

OMA-BS now launches the installed GPU Screen Recorder directly from a dedicated
Python supervisor. It retains Omarchy's monitor/region selection helpers and
webcam window styling. Choosing a mic affects this recording only; system audio
defaults are unchanged. Camera and encoder diagnostics go to
`~/.config/oma-bs/capture.log`.

The supervisor holds a per-app file lock throughout selection, capture, and save.
Repeated starts are rejected. New-session stop requests signal only the encoder
it started, using SIGINT so the video can finalize. Its camera is closed when
capture ends or fails, independently of widget polling. Closing the popup or
reloading its UI does not own the recorder's lifetime.

Output is a new MP4 in `~/Videos/OMA-BS`. No automatic normalization or startup
audio mute is applied to new captures. Native gallery/export features from 0.2.0
and the dependency migration/rollback fix remain available.

## Scope and verification

The webcam is still a separate native overlay window: select a display or region
to include it. Selecting a single window through the portal excludes it. This
release does not yet provide a composited native scene, independent source files,
or native multistreaming. The advanced studio still opens in the browser.

Tests run the real supervisor with simulated camera/recorder executables and a
real video fixture. They cover picker cancellation, duplicate-start rejection,
camera removal during recording, camera cleanup after stop/unexpected exit, and
an unrelated camera remaining alive. Other tests cover device validation,
geometry, actual FFmpeg exports, and updater migration/rollback. These are not
GPU, physical-camera, or Wayland integration tests; the device smoke test remains
necessary. Qt syntax parsing and Omarchy manifest/folder validation are also run.

## Update and smoke test

Stop recording, finish exports, and close the advanced studio before running
`python3 oma-bs/scripts/update-local` from the extracted archive. The updater
backs up replaced files under `~/.local/state/oma-bs/backups/before-0.3.0-*` and
refuses to update during an OMA-BS capture selection or save.

1. Open **Inputs & camera**, pick a mic/camera, and use **Display**, **Both**, and
   **Webcam on next take → On** for a short test recording.
2. Use **Close webcam now**; verify the camera light goes off while capture stays active.
3. Stop and play the result in **Gallery & edit** to check picture and audio.
4. On another short take, stop with the camera open; verify it closes automatically.
