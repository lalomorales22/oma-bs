# OMA-BS 0.2.0 — native gallery and editing

Open **Gallery & edit** in the dropdown, or select a recent recording.

- Expanded native panel with separate video/image tabs and filename search.
- Optional inline video playback with seek, play/pause, and sound toggle.
- Image preview, video thumbnails, duration, and resolution.
- Trim using seconds or the current playback position. Optional audio removal.
- Export a new MP4 into `~/Videos/OMA-BS/Exports`, keeping the original untouched.
- Completed exports appear in the gallery; incomplete export files stay hidden
  and are removed on handled failure/interruption.
- Preview playback releases when the popup closes. Exports continue while it is
  closed, provided the shell/plugin keeps running.
- The browser launch is now labeled **Advanced studio · opens in browser**.

The updater retains 0.1.3's dependency migration and rollback behavior, and backs
up replaced files under `~/.local/state/oma-bs/backups/before-0.2.0-*`.
Stop recording, finish exports, and close the advanced studio before updating.

## Requirements and scope

Native exports require FFmpeg/ffprobe with the libx264 encoder. Inline playback
requires Qt Multimedia and its media backend. Missing Qt Multimedia affects only
the optional preview component, with a thumbnail/external-player fallback.

This is basic range editing, not a full native timeline. Scene composition,
independent synchronized source tracks, and native multistream controls remain
future milestones. The stock Omarchy recorder integration is unchanged.

## Validation

The Python suite exercises actual FFmpeg trim/mute outputs, source preservation,
failed-output cleanup, and gallery inclusion, plus updater migration/rollback and
camera lifecycle logic. Full Quickshell playback and layout still require a smoke
test on the Omarchy device; the development runtime is not that desktop. A real
process-identity test is skipped where its PID namespace differs from `/proc`.
