# OMA-BS 0.1.2 — branding and camera cleanup

- Restores the working QML On/Off control and shell `opened` contract.
- Adds an always-available native **Close webcam now** action. It targets only
  same-user mpv V4L2 windows with Omarchy's exact WebcamOverlay title.
- Turning webcam Off also requests closure of an existing native overlay.
- Tracks native camera process identities during capture; requests closure if
  recording ends outside the panel. Signals use Linux pidfds and start-time checks.
- Keeps pending picker state separate from recording-ended state.
- Stops claiming that a file was saved solely because the Stop command ran.
- Renames studio header, welcome, page title, PWA name, camera-page messages,
  error UI, and exported filenames to OMA-BS. Storage keys deliberately unchanged.
- Gives the inherited studio a muted steel accent instead of lime neon.
- Adds idle **Release camera & mic** in the studio; releases those sources after
  recording finishes when not also streaming. Reload no longer auto-activates
  remembered camera/microphone devices.

## Install over 0.1.0

Stop recording and close the studio browser tab first. Extract this archive into
a fresh directory under Downloads, then run `python3 oma-bs/scripts/update-local`.
The updater backs up replaced files, preserves node_modules and recordings, and
reloads only this plugin. It does not install npm packages or publish anything.

## Test scope and remaining work

Manifest and backend tests run in the development environment. Quickshell rendering,
physical camera release and the studio production build need host testing. The
development runtime does not expose matching process IDs through mounted /proc;
the real-process identity smoke test skips there. No claim of device validation.

The unexpected recorder exit around a game launch is not yet diagnosed. The
backend writes wrapper output to ~/.config/oma-bs/capture.log, but the upstream
recorder may suppress its own diagnostic output. A fresh host log will be needed.

Recording still uses Omarchy's shared wrapper and global recorder detection/stop;
do not run another native recorder at the same time. Independent process ownership,
synchronized raw tracks, and a unified filesystem/browser gallery are not included.
The webcam overlay is a separate desktop window, not a composited camera layer in
portal window-only recordings.

## Dropdown-first direction

Next: native Capture / Gallery / Live / Edit sections in an expandable panel,
device selectors and meters, reliable session-owned recording, persistent media
bridge, then synchronized sources and scene composition. The browser editor is
still a separate view in this release; it has not been embedded in the dropdown.
