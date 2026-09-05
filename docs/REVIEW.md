# 0.7.0 review scope

0.7.1 interface follow-up: all eleven QML files pass syntax parsing, and the four
new shared controls resolve against the real Omarchy UI sources. Eight existing
runtime/updater tests pass, including migration and rollback. The new interface
still needs a visual check in the user's running shell. Recording, streaming,
and browser code did not change in this interface update; the engine checks
below describe the 0.7.0 baseline.

This is a development release, not a claim of a completed security audit or
provider certification. The public-release gate includes real Omarchy hardware
and live-platform checks in RELEASE-CHECKLIST.md.

## Addressed in this release

- Native stream destinations use independent bounded queues so a stalled network
  worker cannot block the backup or another destination. The supervisor owns
  capture/worker lifetimes; stop-stream and stop-recording have distinct behavior.
- RTMPS enables server certificate verification. Stream keys and private URL
  components travel in owner-only temporary FFmpeg preset files, not arguments
  or raw network logs. Failed workers are cleaned up; generic status is returned.
- Browser relay previously bound all interfaces and allowed broad cross-origin
  access. It now binds 127.0.0.1 and checks peer, Host, and Origin; the Vite relay
  proxy enforces the same local policy. This is local access control, not isolation
  from other processes running as the same user.
- Browser ingest and per-destination buffers are bounded. Duplicate configuration
  cannot spawn a second relay in one session. Shutdown closes owned workers.
- Missing root license, attribution, repository CI, current browser docs, and
  marketplace preparation files have been supplied.
- Four high-severity npm dependency advisories were resolved within existing
  version ranges; a full npm audit then reported zero known vulnerabilities.
  This is a point-in-time dependency check, not a guarantee of future safety.
  The launcher now refreshes existing dependencies when the lockfile changes.

## Validation and remaining limits

Release checks: 56 Python tests passed and one host `/proc` identity check was
skipped because this runner's PID namespace differs from its mounted `/proc`.
Four Node bridge/relay tests and 16 browser state tests passed. Browser TypeScript
and production build passed; seven QML files parsed successfully and the real
Omarchy plugin validator accepted the source. The skipped identity check remains
part of device validation. Full npm audit reported zero known vulnerabilities
after the dependency update.

Automated tests exercise real FFmpeg H.264/AAC output to local RTMP receivers,
multiple destinations, connection failure isolation, source-audio preservation,
stream toggling under the recording supervisor, request restrictions, and private
credential transport. Browser build/type checks and QML syntax are separate gates.

This environment does not run the user's Omarchy shell, GPU, webcam, microphone,
or platform accounts. A simulated recorder checks supervisor behavior; it cannot
prove GPU Screen Recorder works with every installed GPU/driver version. RTMPS
certificate options are checked in generated commands; no external RTMPS provider
handshake or audience playback was tested here. “Sending” reports advancing muxed
media output, not proof that a platform has published a broadcast to viewers.

The local backup is mandatory during native streaming. Disk/write failure stops
capture; network failure alone does not. FFmpeg remuxing and source extraction
need free disk space after capture. Unexpected power loss may leave an unfinished
transport file; raw files are retained for recovery, with no automatic deletion.

Keys are not encrypted at rest. Same-user processes can read them. A hard crash
can leave owner-only temporary presets, and browser-imported keys remain in its
local storage until removed there. Git and the plugin archive must never include
these runtime files. Updater backups may also contain old application source;
they are not a replacement for a user's media backup.

The optional browser's phone-camera mode deliberately exposes a Vite development
server on the LAN when explicitly requested; it is not an internet-facing service.
Its third-party chat and AI integrations are optional, experimental, and not
certified by this review. No account credentials or external broadcasts were used
for automated validation. Native captures do not use those online integrations.
