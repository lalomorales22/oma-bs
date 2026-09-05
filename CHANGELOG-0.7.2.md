# OMA-BS 0.7.2

Security and reliability follow-up to the 0.7.1 interface release.

- Restrict native media probing/rendering to local FFmpeg protocols; publish trims
  without overwriting existing exports.
- Harden optional phone pairing: full random UUID, matching Origin/Host, explicit
  HTTPS LAN mode, one participant per role, room/message/buffer limits, heartbeat,
  and safe malformed-frame handling.
- Handle oversized WebSocket frames in the browser relay and proxy without an
  unhandled server error. Force uploaded stream input to WebM/Matroska on a pipe.
- Never embed environment API keys in browser builds. Optional keys remain an
  explicit browser Settings choice.
- Preserve opening WebM chunks while connecting and bound the upload queue.
  Mix live input audio into one track; keep the local archive on relay failure.
- Improve browser source/recorder cleanup, save duration metadata, retain takes
  from removed sources, and keep navigation locked while recording finalizes.
- Keep phone pairing stable across parent renders; replace the camera track when
  flipping; add phone camera/mic stop and disconnect cleanup.
- Use account-supplied ingest URLs for new destinations; clear keys when changing
  platforms, validate stored profile shape, retain intentionally empty lists, and
  require every enabled destination to be complete. Native URL/key limits now
  match the relay's 900-character limit.
- Add focused security regressions and current marketplace requirement mapping.

Known limits and pending hardware/account checks are in
[the review](docs/SECURITY-REVIEW-0.7.2.md). Stop captures/exports and close the
browser studio and relay before updating, then restart the Omarchy shell.
