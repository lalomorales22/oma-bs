# OMA-BS 0.5.0 — one dock, native audio and composition

The dropdown now has a five-icon dock: **Video · Images · Audio · Editor · Layers**.
Switch sections within the existing panel. The fixed footer and scrolling middle
from 0.4 remain, so longer editing controls do not hide the folder button.

## Audio and thumbnails

- Separate take FLACs appear in Audio, labelled with the recording name.
- Audio in `~/Music` and `~/Music/OMA-BS` is also available (FLAC, WAV, MP3,
  M4A, AAC, OGG, Opus).
- Recent files show tiny actual thumbnails. Audio gets a waveform of its first
  30 seconds. The first 12 files receive generated previews; all 50 remain searchable.
- Select a file to preview in the same panel. Audio playback starts only when
  you press Play; closing the gallery releases playback.

## First native composition editor

- Use a video/image as base, pick 16:9, 9:16, 1:1, or 19:6.
- Crop to fill or fit the full image. Drag the base to frame its crop.
- Add up to eight image/video/audio layers, position/size visual overlays,
  change their crop, and bring a selected layer to the front.
- Edit source start, timeline start, layer length, and volume. Length changes
  keep layer ranges within the composition. Added video layers start muted.
- Adding a take's separate source audio mutes its mixed base track to avoid doubling.
- A still layout preview shows arrangement; **Render preview** creates a small MP4
  to check motion and sound inside the gallery. Full export renders a new MP4.
- **Save edit** preserves one active composition across shell restarts. Existing
  source files are never modified; missing sources produce a useful render error.

The browser studio remains available. This release adds a real native composition
path, not the browser's entire editor. Multi-clip splitting, live canvas scrubbing,
text/keyframes/transitions, independent camera video, and multistreaming remain
future work. Preview renders are kept in Exports alongside full renders.

## Validation and installation

Real FFmpeg tests check overlay pixels before/during/after the selected time range,
all four aspect ratios, image/video layers, delayed audio and volume, real waveform
generation, source preservation, rejected invalid edits, and failure cleanup.
The capture, audio-source, export, and migration/rollback regression suite is also
run. QML syntax and the actual Omarchy plugin validator are checked. Desktop
interaction, theme rendering, and actual device capture still need the Omarchy machine.

Finish recording, audio preparation, and exports; save your edit and close the
advanced studio before updating. The updater backs up replaced files under
`~/.local/state/oma-bs/backups/before-0.5.0-*` and includes all new QML/backend files.
