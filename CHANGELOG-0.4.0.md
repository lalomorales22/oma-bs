# OMA-BS 0.4.0 — full footer and separate audio

## Dropdown fix

Removed the compact popup's fixed 680-pixel height cap. It now sizes to its
content within the available screen area. **Open recordings/images folder** and
**Advanced studio** live in a fixed footer outside the scrolling content, keeping
them fully visible. A themed scrollbar appears when the middle section is longer
than the available space. The native gallery also respects its minimum content
height when source-file controls are present.

## Separate audio for new takes

The widget enables **Separate audio files** by default; its switch is under
**Inputs & camera**. With both audio inputs enabled, GPU Screen Recorder is
launched with separate desktop and microphone tracks. After stopping:

- The untouched multitrack source remains as `Sources/<take-name>/capture.mkv`.
- Separate `desktop.flac` and `microphone.flac` files retain their individual levels.
- FLAC audio is resampled to 48 kHz and padded to the source timeline start.
- A normal mixed MP4 appears in the regular gallery without re-encoding its video.
- `session.json` records source roles, original track start times, and result status.
- **Open last take’s source files** and the gallery's **Open source audio files**
  buttons open the matching source directory.

Only enabled inputs are saved. A microphone-only take produces one microphone
file; a silent take produces no audio files. The command line opts into this
workflow with `--separate-audio`. Existing recordings and mixed-only capture
remain supported. Preparation uses extra time/storage; the camera is closed
before this work begins. Missing/unexpected streams produce an error instead of
mislabelled audio. The master remains available if preparation fails.

This does not unmix old recordings, record an independent webcam video, or add a
native audio timeline/multistream engine. The advanced studio remains browser-based.

## Validation and update

Real FFmpeg tests use separate 440 Hz and 880 Hz tones to check source isolation,
the mixed preview, and preservation of a delayed audio input. Tests also verify
that the master is unchanged, existing previews are not overwritten, and a
wrong stream count is rejected. The supervisor integration test checks the
complete source-capture-to-gallery path. Previous lifecycle, export, and updater
regressions remain covered. QML syntax and Omarchy plugin folder/manifest
validation are checked; final desktop layout and real device capture require
testing on the Omarchy machine.

Stop recording, finish audio preparation and exports, and close the advanced
studio before running the extracted `scripts/update-local`. Replaced files are
backed up under `~/.local/state/oma-bs/backups/before-0.4.0-*`.
