# 0.7.6 — private RTMP publishing repair

- Device trace identified a concrete failure: FFmpeg 9.0.1 read the preset but
  reached RTMP with empty `app` and `playpath`, publishing an empty stream name.
- Replace CLI connection presets in both streaming engines with a shared native
  transport using `avio_open2` and an explicit private options dictionary.
- Credentials reach the sender through an inherited pipe, never argv. Private
  connection JSON stays owner-only and is removed when its destination closes.
- Preserve RTMPS certificate checks, bounded queues, local backup, audio mixing,
  and independent destination shutdown. Suppress raw library errors and FFREPORT.
- Compile the small sender with gcc against installed FFmpeg headers. Cache it
  outside the plugin and rebuild when its source or FFmpeg library ABI changes.
  The updater checks/builds before disabling the installed plugin.
- Add real wire assertions for nonempty application/publishing fields, synthetic
  video plus silent AAC delivery, and rejection of an untrusted TLS certificate.

Local tests do not certify Twitch account access or public playback. A successful
device broadcast and the remaining release checklist are still required before
marketplace submission. The earlier standalone Twitch checker still exercises
the old preset path; use the updated app to test this repair.
