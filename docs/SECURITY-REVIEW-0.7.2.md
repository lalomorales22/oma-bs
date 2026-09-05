# OMA-BS security and submission review — September 5, 2026

Scope: native QML controls, Python capture/editor/streaming helpers, updater and
runtime layout, browser recorder and phone pairing, Vite routes, Node/FFmpeg
relay, npm dependency audit, release archive, and marketplace submission files.
This is a source review with regression tests, not an independent certification.
Tests run in a separate Linux environment without the user's camera/GPU/accounts.

## Findings repaired in 0.7.2

| Finding | Repair and evidence |
| --- | --- |
| Phone signaling admitted arbitrary origins, roles, and short-token rooms without resource limits | Matching Origin/Host, local default or explicit private-LAN HTTPS mode, full UUIDv4 token, one desktop plus one phone, four-room limit, bounded/rate-limited signaling and heartbeat. Real WebSocket tests reject a third peer and foreign origin. |
| Oversized WebSocket frames could raise unhandled errors | Error handlers on signaling, proxy, and relay clients. Oversized phone frame regression closes that client and verifies the server still accepts a fresh room. |
| Environment Gemini key was compiled into browser JavaScript | Removed key injection; runtime Settings remains explicit. Build verification uses a fake sentinel and checks that it does not appear in generated assets. |
| FFmpeg auto-detection could follow network references in misleadingly named media | Native probe, thumbnail, trim, and scene inputs use file/pipe allowlists. Relay input is forced Matroska/WebM over pipe. A real disguised-HLS test verifies zero requests to its local HTTP target. |
| Trim publication could replace a colliding output | Atomic no-overwrite link; a real encode regression creates a competing output and verifies it survives. Originals and partial cleanup are also tested. |
| Browser relay lost the WebM header while connecting | Ordered, bounded upload queue retains opening chunks; tests cover order, overflow, send errors, and cleanup. |
| Browser stream passed multiple audio tracks to MediaRecorder | Web Audio mixes live inputs into one track with gain headroom and silence for empty scenes; graph/ownership test verifies cleanup does not stop input-owned tracks. |
| Recorder/source lifecycle and stale state could lose takes or retain hardware | Current-source references, unmount/late-permission cleanup, independent recorded-source metadata, elapsed-time durations, finalization navigation lock, and camera/mic release. Hardware behavior requires the checks below. |
| Phone camera flip restarted pairing and parent renders could reset its session | Stable callbacks/session effect and sender track replacement; explicit stop and disconnect cleanup. Actual phone test remains pending. |
| Stream profiles could be damaged, silently incomplete, or use guessed provider endpoints | Shape/size checks, empty-list preservation, account-supplied new URLs, key clearing on provider change, completeness check, matching native/relay length limits. |

Existing capture ownership checks, private profile/preset handling, bounded
independent native stream workers, safe updater rollback, and external npm runtime
placement were reviewed and retained. No shell interpolation of ingest credentials
was found in the reviewed launch paths. Local media protocol controls do not block
every local-file reference and are not a decoder sandbox.

## Automated evidence

- Python native suite: 59 tests, 58 passed and one environment-specific PID
  namespace identity check skipped. Includes real FFmpeg editing and streaming.
- Node bridge/relay suite: four tests passed, including real WebM audio/video to
  a local RTMP listener while another destination fails.
- Browser TypeScript passed, all 24 regression tests passed, and the production
  build passed. The fake environment-key sentinel was absent from build assets.
  The npm audit reported zero known advisories in this review.
- All 11 QML files parsed and the actual pinned Omarchy plugin validator passed.
  Validator source: Omarchy commit `493067741e081c3b09082da6bfd51e99ec24ef00`.
- The public initial 0.7.1 [GitHub CI run](https://github.com/lalomorales22/oma-bs/actions/runs/33960715411)
  passed. The 0.7.2 commit must pass its own CI after publication.

## Marketplace requirement mapping

Checked against the [publishing guide](https://plugins.omarchy.org/publish.html)
and current [issue form](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/.github/ISSUE_TEMPLATE/submit-plugin.yml).
Form snapshot SHA: `4b2bebd1beb39ebf61cc2a6496897ff02d94e144`.

| Requirement | Repository evidence / status |
| --- | --- |
| Public GitHub repository | `https://github.com/lalomorales22/oma-bs` exists; reviewed repairs still need publication. |
| Valid root manifest and entry point | `manifest.json`, `BarWidget.qml`; actual Omarchy validator used. |
| README and license | `README.md`, MIT `LICENSE`, `THIRD-PARTY-NOTICES.md`; owner must confirm redistribution rights. |
| Safe install and removal | README instructions, no automatic system-package installer/hooks, dependencies outside plugin, guarded updater with backup/rollback; clean-device lifecycle test pending. |
| External dependencies disclosed | README and third-party notices list native/browser requirements; optional third-party services documented. |
| No unrelated config overwrite without consent | Explicit Omarchy registration and user-requested settings/update actions; no system audio-default changes. Owner reviews form confirmation. |
| Category and 1–3 tags | Prepared draft: Productivity; Bar, Media, Quickshell. |
| Ownership/approval acknowledgments | Present in submission checklist; owner confirmation remains required. |
| Preview | Optional; add real redacted screenshots before submission if desired. |
| Submission route | Marketplace issue form, automatic repository validation, then maintainer review. Not yet submitted. |

## Remaining release checks

1. On the real Omarchy device, update/restart and verify display/window/region
   recording, input selection, camera dismissal, automatic stop, inline playback,
   crop/layers/export, and final saved media. Repeat phone pairing/flip/stop if
   advertising that optional feature.
2. Test at least two real destinations, including RTMPS certificate/handshake,
   platform dashboard playback, disconnect isolation, local backup, and stop.
   Local tests do not prove account access or provider compatibility.
3. Run clean install, enable, update, disable, remove, reinstall in a test account;
   confirm personal media/settings survive removal. Confirm permissions and hide
   all keys in screenshots/logs.
4. Publish this release, wait for its GitHub CI, and complete the owner's issue
   form confirmations. The current chat GitHub connection is read-only.

Known product limits: browser long takes accumulate in memory; browser/native
galleries and capture controls are separate; browser streaming audio sources are
selected at start; native webcam video is not an independent source recording;
native editor compositions are not live scenes. Experimental chat/AI provider
availability, real mobile browsers, and OS decoder/driver vulnerabilities are
not verified by these local tests. Marketplace approval itself is not an audit.
