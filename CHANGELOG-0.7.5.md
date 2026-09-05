# OMA-BS 0.7.5 — private streaming error diagnostics

Inspection of a reported Twitch failure found that native destination workers
discarded FFmpeg stderr and reported a generic connection/credentials failure.
That made network, TLS, media, and authentication issues indistinguishable. A
local recording starting does not prove that a destination accepted the stream.

- Drain FFmpeg stderr in a dedicated worker and classify known messages in a
  bounded in-memory buffer. Only fixed error-category messages and exit codes
  enter status; raw output, server messages, keys, and ingest paths are discarded.
- Distinguish DNS, connection refusal, timeout, TLS, publishing rejection, missing
  tracks, invalid media, incompatible codec, and rejected FFmpeg options.
  Unknown errors still use the generic message and process exit code.
- Preserve the last failed destination status after the recording stops. The
  Stream tab shows it; starting a new streaming capture resets that history.
- Keep the existing private FFmpeg presets, explicit destination enable/save,
  native keyboard input, independent destinations, and local backup behavior.

Validation includes real local RTMP audio/video fan-out and failure isolation,
connection-refused classification, synthetic credential-bearing errors, and a
large stderr burst that must drain without exposing raw text or hanging a worker.
Native tests, updater checks, QML syntax and actual Omarchy validation are gates.
These tests do not establish the cause of the user's Twitch failure or validate
a real Twitch account, RTMPS service, GPU capture, or live platform playback.

After update/restart, retry once and read the failed destination's message in
Stream. The error remains after Stop both & save. Share the message/category,
not keys or unfiltered configuration/logs.

Reference: [Twitch broadcast URLs and keys](https://dev.twitch.tv/docs/video-broadcast/)
and [FFmpeg RTMP protocol options](https://ffmpeg.org/ffmpeg-protocols.html#rtmp).
The native handoff uses RTMP app/playpath/tcurl options in private presets so the
stream key is not exposed in process arguments. The localhost test verifies
delivery with this path; platform-side acceptance still needs device evidence.
