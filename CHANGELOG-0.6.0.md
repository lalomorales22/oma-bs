# OMA-BS 0.6.0 — editor and streaming setup

- Consolidated the former Editor and Layers pages. The Editor now has its canvas,
  layers/audio list, per-track controls, and exports together.
- Replaced the fifth dock button with **Stream**. Video, Images, and Audio remain.
- Added saved destination cards with platform choice, RTMP/RTMPS URL, masked
  stream key, enable/disable, and removal. Up to 16 destinations are supported,
  including multiple accounts on the same platform.
- Platform choices: Twitch, YouTube, Kick, X, TikTok, Custom. Paste the exact
  ingest URL supplied by your account; the native page does not guess endpoints.
- Incomplete entries can be saved for later. Changing platforms clears that row's
  URL/key. Unsupported protocols and FFmpeg relay delimiters are rejected with
  messages that do not echo credentials.
- Saved credentials live outside the plugin in `~/.config/oma-bs/streaming.json`,
  mode 0600. They are not encrypted. Save uses stdin, not process arguments, and
  capture status does not expose the new credentials.
- **Save & open browser studio** keeps the advanced app optional. Its Stream
  settings now offer an explicit **Load saved OMA-BS destinations** button,
  replacing its current list. Import uses a read-only, loopback-only bridge with
  Host, Origin, request-header, and fetch-site checks. No broadcast starts on import.
- Added TikTok as a browser destination choice; it requires account-supplied URL/key.
- Native Stream manages setup only; the browser's existing relay/Go Live flow
  still performs broadcasts. No native broadcast status or engine is claimed here.
- The header shows **0.6.0** so loaded UI is easy to identify. Backend imports no
  longer write Python bytecode into the shell-watched plugin directory.

Finish captures and exports, save edits, and close the browser studio before
updating. After the updater succeeds, run `omarchy-restart-shell` to refresh all
loaded QML components. The updater preserves settings and backs up replaced
files under `~/.local/state/oma-bs/backups/before-0.6.0-*`.

Validation covers private settings round trips, invalid-input preservation,
secret-free save output, bounded payloads, symlink rejection, and the browser
bridge's denied cross-origin/LAN requests. Existing capture/editor/updater
regressions, QML syntax, and the real Omarchy plugin validator are also checked.
Live streaming to third-party platforms requires testing with the user's accounts.
