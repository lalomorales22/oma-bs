# OMA-BS advanced browser studio

The optional browser companion to the native Omarchy widget, adapted from Lalo
Morales's Chroma Canvas. Open **Advanced studio · opens in browser** from the
widget. Its writable runtime and npm dependencies live outside the plugin folder;
the launcher opens `http://127.0.0.1:4173`.

## Features and storage

- Screen/window, webcam, and microphone sources with canvas overlays, chroma key,
  scene controls, and per-source recording.
- Timeline editing, transforms, text, waveforms, undo/redo, and WebCodecs export
  where supported; browser gallery and IndexedDB project storage.
- RTMP(S) multistreaming through the local relay. One canvas encode feeds bounded,
  independent destination workers.
- Optional phone camera and experimental chat/AI integrations. These third-party
  features are not required for native capture, editing, or streaming.

Download important media and exports: clearing browser storage can erase projects.
Native and browser capture have separate controls; stopping one does not stop the
other. Their galleries also use different storage. Import/export media explicitly
when moving between them. Native streaming uses its selected capture settings,
not the browser canvas or the native editor's exported composition.

## Browser streaming

Native streaming needs no Node.js relay. Browser streaming additionally requires
FFmpeg and the relay. After opening the studio, in a separate terminal:

```bash
cd "${XDG_DATA_HOME:-$HOME/.local/share}/oma-bs/studio"
npm run relay
```

In Recorder Studio's Stream settings, add ingest URLs and keys or explicitly choose
**Load saved OMA-BS destinations · replaces this list**. Press the browser's Go Live
control to broadcast its canvas. Saving/importing alone never goes live. Watch
each platform dashboard to confirm audience playback. Use account-specific RTMP(S)
ingest URLs, not HTTPS page URLs. The relay accepts 1–16 destinations and up to
900 characters per URL/key. Failed connections require a manual restart.

The relay listens on `127.0.0.1:4000`, checks local origins, bounds buffers, and
passes credentials through temporary owner-only FFmpeg presets. RTMPS verifies
certificates. Imported keys remain in browser local storage and are not encrypted.
Do not share storage dumps or credentials. Stop the relay with Ctrl+C before
updating. Stop capture and click Release camera & mic when finished with sources.

## Development

Copy `studio/` to a separate folder first. Never install npm dependencies inside
an installed plugin: its validator rejects npm's symlinks. Node.js 22+ is expected.

```bash
npm ci
npm run dev       # local development, port 3000
npm run relay     # separate terminal; optional streaming/chat relay
npm run typecheck
npm test
npm run build
```

Root GitHub CI checks an external browser source copy. The native launcher keeps
port 4173 to preserve browser storage; historical `chromacanvas` storage names
remain intentionally for compatibility with existing projects and settings.

`npm run dev:phone` explicitly exposes an HTTPS Vite development server on the LAN
for phone-camera pairing. Do not port-forward it or treat it as an internet-facing
production service. Native-key and stream-relay routes remain local-only. Use a
local URL for the desktop control page and the generated LAN URL for the phone.
Optional third-party chat/AI integrations are experimental; service availability
and pricing may change. API keys configured in the browser or build are visible
to the client.

See root [README](../README.md), [license](../LICENSE), and
[notices](../THIRD-PARTY-NOTICES.md). Old planning notes in this directory are
historical Chroma Canvas documents, not current release-readiness claims.
