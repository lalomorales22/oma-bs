# OMA-BS 0.7.0 — native streaming

- Circular Stream control beside Record uses the selected display/window/region,
  microphone, desktop audio, camera overlay, and frame rate.
- One H.264 capture feeds a local backup and up to 16 saved RTMP(S) destinations.
- End live stops network outputs while recording continues. Stop stream & save
  ends the take and prepares the MP4 plus separate enabled audio sources.
- Stream tab reports connecting, sending, partial failure, and stopped states per
  destination. Saving settings never starts a broadcast.
- Bounded destination queues isolate slow/failed connections from other streams
  and local backup. Keys are passed via temporary owner-only FFmpeg presets,
  excluded from process arguments/logs; RTMPS verifies the server certificate.
- Browser relay now binds to loopback, validates client origins, bounds buffers,
  and isolates destinations. Native and browser streaming remain separate sessions.
- GitHub CI, license/attribution, publication checklist, and marketplace issue
  draft added. Package metadata and browser documentation use OMA-BS branding.
- Browser dependency advisories fixed within existing version ranges. The launcher
  refreshes installed dependencies when the lockfile changes.

First-version limits: start a fresh take with Stream; an ordinary recording
cannot become a live stream midway through it. Native webcam is a separate
visible overlay and is excluded from single-window capture. Use display/region
to include it. Native editor compositions are exported edits, not live scenes.
Provider dashboards must confirm viewer availability; sending media alone cannot
verify a platform's publication state. Failed destinations need a manual restart.
