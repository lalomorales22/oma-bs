# OMA-BS

**Omarchy Broadcast Studio** is a native Omarchy Quattro bar plugin backed by the
capture stack Omarchy already trusts. It turns screen recording into a two-click
flow, with a native gallery and basic video editing. The advanced browser studio
is adapted from Chroma Canvas and branded OMA-BS.

## v0.7.6 fixes empty publishing names

FFmpeg 9 read our connection preset but published with an empty application and
stream name. Native and browser streaming now use a small transport worker that
passes the private connection options directly to libavformat. Keys stay out of
process arguments and raw logs. RTMPS certificate verification remains enabled.

The updater builds the worker in `~/.cache/oma-bs/transport`, outside the plugin.
On Arch, install its build dependency with `sudo pacman -S --needed gcc ffmpeg`.
Actual Twitch playback still requires the account/device test; local tests verify the RTMP publishing fields,
audio/video delivery, failure isolation, and rejection of untrusted certificates.

### Destination enable/save

Each destination has **Enable & save** and **Disable & save** actions. Enabling
again leaves it enabled. Save reads back the profile and confirms how many
destinations are ready, or explains whether a channel is disabled/incomplete.

The native popup now uses Omarchy’s keyboard-capable panel. Stream URL/key
fields accept typing and pasting and retain changes immediately.

See [security review](docs/SECURITY-REVIEW-0.7.2.md) for fixes, validation, and
remaining device checks. See [changelog](CHANGELOG-0.7.6.md) for this update.

## Features

- Native top-bar widget and themed popup panel
- Outlined controls and padded cards; matching oval Record and Stream buttons
- Slim themed scrollbar fades away when idle; no permanent grey track
- Popup grows to the available screen height; folder/studio buttons stay in a fixed footer
- Middle content scrolls with a themed scrollbar when the panel cannot fit it all
- Display, portal-based window/display picker, and region capture
- Silent, desktop, microphone-only, or desktop-plus-microphone modes
- **Inputs & camera**: choose the recording microphone and camera, plus 30/60 fps
- Last-used input/size/frame-rate choices are restored; the webcam stays off on reload
- New takes can keep separate desktop/microphone FLAC files and a multitrack MKV source
- A mixed MP4 remains in the regular gallery; **Open source audio files** opens its source folder
- Optional webcam overlay in small, medium, or large mode
- Oval Stream button beside Record uses the same capture/input choices
- One H.264 capture feeds a local backup and independently buffered RTMP(S) destinations
- End live keeps recording; Stop both & save ends both and prepares source audio
- Per-destination connection and media progress in the Stream page
- Cancel an open capture picker; dismiss the camera while screen recording continues
- Expand **Gallery & edit** directly from the dropdown, or click a recent file
- Five-icon dock: Video, Images, Audio, Editor, and Stream share the same panel
- Layers and audio tracks live directly below the canvas in Editor
- Stream stores up to 16 destinations for Twitch, YouTube, Kick, X, TikTok, or custom servers
- Server URLs, masked stream keys, and per-destination enable switches
- The optional browser studio can explicitly import the native saved destinations
- Filename search across the 50 most recent files; thumbnails for the first 12
- Audio gallery finds separate take FLACs and audio in `~/Music` / `~/Music/OMA-BS`
- Real waveform thumbnails show the first 30 seconds; inline playback plays the whole file
- Inline playback, seek bar, sound toggle, image previews, and media information
- Trim with start/end seconds or **Set start/end here**, and optionally remove audio
- Export a new H.264/AAC MP4 to `~/Videos/OMA-BS/Exports`; originals are preserved
- Native canvas shapes: 16:9, vertical 9:16, square 1:1, and ultrawide 19:6
- Crop/fit and frame a base image/video; add up to eight image, video, or audio layers
- Drag visual layers, adjust size/crop, source start, timeline start, duration, and volume
- Render a small preview for inline playback, or export the full-size composition
- Save one active edit and restore it after shell reload
- Advanced studio remains available through **Advanced studio · opens in browser**

Playback stops when you close the panel or return to capture. An export keeps
running when the popup closes, with its result shown when you reopen it. Finish
exports before updating or restarting the shell. Independent camera video remains
future engine work; native streaming is available in this release.

### Editing in the dropdown

Choose a file in **Video** or **Images**, then **Use as base**. This begins a new
composition and replaces the current in-panel edit. Pick a canvas shape, drag
the base picture to frame its crop, or switch **Crop to fill** to **Fit whole image**.
The source files always remain unchanged.

Use **+ Video**, **+ Image**, or **+ Audio** to browse the gallery and **Add layer**.
Click a track to edit its source start, timeline start, and length. Visual layers
can be dragged around the canvas and sized with width/height percentages. Crop
X/Y controls frame content inside each layer; **Bring to front** changes stacking.
Audio volume is 0–200%; 0 mutes a track. Added video layers start muted. Adding
a separate audio file from the base recording's own source folder mutes the
base's mixed audio to avoid playing it twice. Add both source files when you
want to rebuild both microphone and desktop audio.

The canvas is a **still layout preview**, showing every visual layer's first-frame
thumbnail regardless of its timeline start. Use **Render preview** to check actual
motion, timing, and sound in the gallery. Preview renders are small MP4s in Exports;
they are kept until you remove them yourself. Full exports use 1920×1080, 1080×1920,
1080×1080, or 1900×600 at 30 fps. These are new H.264/AAC renders, not lossless copies.
Audio layers are summed with a peak limiter. The original stems retain their levels.

**Save edit** saves the active composition to `~/.config/oma-bs/editor-project.json`.
Switching between dock sections retains unsaved work while the shell stays running;
save before reloading or updating. This is a first native composition editor:
no split-tool/multi-clip timeline, transitions, text generator, keyframes, or live
motion scrubbing on the canvas yet. Imported media must be in the supported
Videos, Pictures, or Music folders; move/copy an asset there before using it.

### Stream setup in the dropdown

Open **Stream → Add destination**, choose a platform, and paste the **RTMP/RTMPS
ingest URL** and **stream key** supplied by your platform's live dashboard. URLs
are not guessed: some services issue different endpoints for different accounts.
An HTTPS dashboard/page URL is not an ingest URL. Add multiple destinations,
including several accounts on one platform, and enable the ones for your next
broadcast. Incomplete entries can be saved as drafts. Changing a row's platform
clears its URL and key so credentials are not accidentally reused on another site.

**Save destinations** writes `~/.config/oma-bs/streaming.json` with owner-only
permissions (0600). This is a local plaintext file, not an encrypted credential
vault. Keys are masked by default, hidden again when the panel closes, sent to
the save process over stdin, and excluded from ordinary capture status output.
Save changes before restarting the shell; closing/reopening the dropdown retains
unsaved entries during the current shell session.

**Save & open browser studio** opens the optional studio. In its **Stream**
settings, click **Load saved OMA-BS destinations · replaces this list**. This is
an explicit one-way import and replaces the browser's current destination list;
subsequent browser edits do not update the native settings. The browser stores
its imported list in its existing local storage. The bridge only serves the
explicitly launched local studio through guarded loopback requests, with no
cache or cross-origin access. The standalone/LAN studio does not automatically
gain access to native keys.

Save destinations, choose capture/audio/camera settings, then press the **oval
Stream button beside Start recording**. It starts a new capture, sends it to every
enabled complete destination, and keeps a local backup. An ordinary recording
already in progress must finish before a stream can start. Stream-started takes
can stop and restart their network outputs without ending the local recording;
restarted outputs use the newly saved destination list.

**End live** stops network outputs while local recording continues. **Stop both
& save** ends the take, closes its camera, and prepares the MP4/source audio.
Stream shows connecting/sending/failed states per destination. A failed or slow
destination does not stop the others or the local backup. There is no automatic
reconnect: End live, check settings, then press Stream again. Confirm audience
availability in each provider dashboard; advancing media output cannot prove a
platform has made a broadcast visible to viewers.

Native streaming uses H.264 at approximately 6 Mbit/s, a two-second keyframe
interval, selected 30/60 fps, and a 1920×1080 bounding box. Each destination adds
its own upload bandwidth (roughly 6.2 Mbit/s including AAC, plus overhead).
Sixteen profiles is a configuration limit, not a promise of machine/network
capacity. RTMPS verifies TLS certificates. Native sending supports server URLs
and keys up to 900 characters each. Secrets use temporary mode-0600 connection
files, not process arguments. Normal stop removes these; a crash can leave
private remnants.

Silent takes send silent AAC for stream compatibility; their saved source remains
silent. Desktop-plus-microphone streaming sends a normalized mix, while the
backup retains both tracks. Streaming always keeps separate source audio regardless
of the ordinary recording toggle. It retains `capture.ts`, remuxed `capture.mkv`,
derived FLACs, and gallery MP4, using extra disk. Disk/write failure stops capture
rather than silently losing the backup.

Native editor layers compose exported edits, not live scenes. The native camera
is a separate visible overlay: display/region capture includes it, single-window
capture does not. The optional browser studio has its own canvas and **Go Live**
controls, independent of native capture. Saving/importing profiles never goes
live. Provider access and account-specific credentials are required. Automated
streaming tests use local receivers and never publish to platform accounts.

**Separate audio files** defaults to On in the widget's **Inputs & camera**
settings. Turn it off to keep the smaller, mixed-only recording workflow.
Source files are saved under `~/Videos/OMA-BS/Sources/<take-name>/`:

- `capture.mkv`: the untouched recording with separate enabled audio streams
- `desktop.flac` and/or `microphone.flac`: individual decoded audio, resampled to
  48 kHz and padded to the source timeline start; original levels are retained
- `session.json`: stream identities, timing information, and preparation status

The usual MP4 is created after recording stops, copying the encoded video and
mixing audio for convenient playback. When both inputs are enabled, the preview
mix is normalized by input count to provide headroom. Source audio remains
unmixed. FLAC avoids another lossy encode of the captured AAC audio; it does not
restore detail already lost during capture. Sources use extra disk space, and
long takes need additional preparation time. A failed preparation keeps the MKV
and reports the error in the widget and `session.json`.

Only new recordings made with the option enabled get separate source files.
Older mixed recordings cannot be unmixed by enabling this option. Silent takes
produce the source MKV and video preview without audio files.

## Install on Omarchy Quattro

This repository is the plugin itself. Once it is published, install it with:

```bash
omarchy plugin add https://github.com/lalomorales22/oma-bs.git --enable
```

For local development:

```bash
mkdir -p ~/.config/omarchy/plugins
ln -s "$PWD" ~/.config/omarchy/plugins/lalo.oma-bs
omarchy-shell shell rescanPlugins
omarchy plugin enable lalo.oma-bs
```

For an extracted release, copy its `oma-bs` folder to
`~/.config/omarchy/plugins/lalo.oma-bs`, then validate, rescan, and enable it.
For an existing archive installation, use `scripts/update-local` from a separately
extracted update; it backs up replaced files and moves npm dependencies outside
the plugin. Never copy node_modules into the plugin folder.

Omarchy watches the plugin folder, but QML can remain cached after updates. Save
edits, finish captures/exports, close the browser studio, stop any manually launched
relay, and run `omarchy-restart-shell`. Confirm version 0.7.6 in the popup. If it
is missing, inspect `qs log -p "$OMARCHY_PATH/shell" --tail 100` for `lalo.oma-bs`
errors and validate the installed folder with `omarchy plugin validate`.

### Remove safely

Finish captures/exports and close the studio. Stop a manually launched browser
relay in its terminal with Ctrl+C, then:

```bash
omarchy plugin disable lalo.oma-bs
omarchy plugin remove lalo.oma-bs
```

Omarchy handles removal and its confirmation. Recordings, exports, private settings
in `~/.config/oma-bs`, browser storage, runtime dependencies in
`~/.local/share/oma-bs`, and updater backups in `~/.local/state/oma-bs/backups`
remain outside the plugin folder. Remove unwanted personal media/settings
separately only after backing up what you need. Native and browser-imported keys
are separate copies. No system-package removal is needed to remove the plugin.

## Requirements

New recordings use OMA-BS's own process supervisor with the installed
`gpu-screen-recorder`, Omarchy's region/monitor helpers, and `mpv` for the webcam.
Device enumeration uses `gpu-screen-recorder --list-audio-devices` and
`omarchy-capture-webcam-list`. No system audio defaults are changed.
Native inspection, thumbnails, and exports
require `ffmpeg` and `ffprobe`. Inline playback additionally uses Qt Multimedia;
Arch provides `qt6-multimedia` and the `qt6-multimedia-ffmpeg` backend:

```bash
sudo pacman -S --needed qt6-multimedia qt6-multimedia-ffmpeg
```

Official packages: [Qt Multimedia](https://archlinux.org/packages/extra/x86_64/qt6-multimedia/)
and [FFmpeg backend](https://archlinux.org/packages/extra/x86_64/qt6-multimedia-ffmpeg/).
If the module is missing, the gallery still loads with a thumbnail and external
player fallback; numeric trim and export remain available.

The advanced browser studio needs Node.js 22+, npm, and FFmpeg;
its writable runtime and dependencies live under
`${XDG_DATA_HOME:-~/.local/share}/oma-bs/studio`, outside the plugin directory.
The launcher copies source there and runs `npm ci` on first launch and whenever
the lockfile changes, so dependency updates reach existing installs too. This
can take longer and needs npm registry access. Never run npm install inside the
installed plugin: npm creates symlinks
which Omarchy's plugin validator rejects.

The `scripts/update-local` updater migrates existing dependencies there before
validating the installed plugin. Replaced source files and any pre-existing runtime
dependencies are backed up. The launcher keeps `http://127.0.0.1:4173/` unchanged
so browser-stored projects retain their origin.

## Commands

```bash
scripts/oma-bs status
scripts/oma-bs devices
scripts/oma-bs list video
scripts/oma-bs list audio --thumbnails
scripts/oma-bs start --capture window --audio both
scripts/oma-bs start --capture display --audio desktop --webcam
scripts/oma-bs start --capture display --audio microphone --microphone default_input --fps 30
scripts/oma-bs start --capture display --audio both --separate-audio
scripts/oma-bs start-stream --capture display --audio both --webcam
scripts/oma-bs stop-stream  # network off; recording continues
scripts/oma-bs stop         # ends take and prepares files
scripts/oma-bs webcam-off
scripts/oma-bs studio
scripts/oma-bs inspect "$HOME/Videos/OMA-BS/take.mp4"
scripts/oma-bs export "$HOME/Videos/OMA-BS/take.mp4" --start 2 --end 12 --mute
```

## Test

```bash
python3 -m unittest discover -s tests -v
node --test tests/*.test.mjs
```

## Architecture direction

The QML bar plugin remains tiny and responsive. `scripts/oma-bs` owns capture
state, filesystem access, and native FFmpeg exports. The adapted browser studio
provides the existing scene composition and advanced editing UI.

`scripts/capture_session.py` supervises new recording sessions independently of
the popup. An inherited file lock prevents competing OMA-BS starts. Stop and camera
off requests go to that session through token-specific control files, and only
the supervisor's children receive signals. SIGINT lets the encoder finalize its
file; OMA-BS never force-kills it on a short timeout. The camera closes when the
recorder exits, even without QML status polling. Encoder and camera stderr are
kept in `~/.config/oma-bs/capture.log` for diagnosing early exits.

The capture options follow the upstream
[Omarchy helpers](https://github.com/basecamp/omarchy/tree/quattro/bin) and
[GPU Screen Recorder interface](https://git.dec05eba.com/gpu-screen-recorder/about/).
New sessions retain the raw recorder output without Omarchy's post-capture
normalization or initial audio mute. A single-window portal capture does not
include the separate webcam window; use display/region capture for that overlay.
Frame rate and device choices apply to the next recording.

`scripts/audio_sources.py` derives aligned audio files and mixed playback from a
single recording timeline. It validates the expected stream count before assigning
desktop/microphone labels, retains the master, and publishes outputs without
overwriting existing files. The capture lock remains held through preparation.
The CLI keeps mixed-only recording unless `--separate-audio` is passed.

`scripts/scene_editor.py` validates a composition against the actual source files,
then renders crop/fit, timed overlays, and audio layers with FFmpeg. It publishes
a new output atomically and removes only its own temporary output on failure.

The webcam remains a visible overlay in display/region recordings. Independent
webcam video plus a clean screen feed and a full native multi-clip timeline remain
future milestones. Native editor compositions do not alter live capture output.
`scripts/live_stream.py` manages private per-destination FFmpeg workers and the
local transport backup from the native capture feed.

## Release and contribution

See [release checks](docs/RELEASE-CHECKLIST.md), the
[marketplace submission draft](docs/MARKETPLACE-SUBMISSION.md), and
[review scope](docs/REVIEW.md). This development release requires real GPU, camera,
and provider checks before marketplace submission. Include version numbers and
redacted logs in bug reports; never post stream keys or private media.

Licensed under [MIT](LICENSE). See [third-party notices](THIRD-PARTY-NOTICES.md)
for Omarchy and the browser studio's origins and dependencies.
