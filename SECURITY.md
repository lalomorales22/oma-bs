# Security and privacy

OMA-BS is an unsandboxed desktop plugin running as your user. It can access your
screen, camera, microphone, files, and network through local tools. Install only
reviewed source. Marketplace listing is not a security certification.

## Data and credentials

- Native media lives in your media folders; private capture state and streaming
  profiles live under `~/.config/oma-bs`. Stream keys are plaintext in an
  owner-only file (0600). This does not protect them from other programs running
  as your user. Temporary FFmpeg preset files keep keys out of process arguments.
- Explicit streaming sends media to your enabled RTMP(S) destinations. Prefer
  RTMPS; plain RTMP is unencrypted. RTMPS certificate verification is enabled.
  Use the ingest address issued for your account, not a website page URL.
- Browser projects/media and imported keys use browser storage. Keys are not
  encrypted. Optional AI/chat actions communicate with third-party providers;
  provider keys entered in Settings are visible to client code. Environment API
  keys are not embedded in the compiled client. Do not share storage dumps.
- The optional phone feature uses WebRTC and Google's STUN server for connection
  discovery. The pairing QR contains a capability token: share it only with your
  intended phone. Default studio/relay servers bind to loopback. Explicit HTTPS
  phone development mode exposes Vite on your LAN; do not port-forward it or use
  it as a public production server. Native key/relay routes stay local-only.
- Native and browser recorders are separate engines. Stop each active engine,
  release sources, and save/download work before closing or updating.

## Scope and limitations

Use current Omarchy, GPU Screen Recorder, FFmpeg, mpv, Qt, Node, and browser
packages. Media decoders and GPU drivers are outside this repository's security
boundary. Local protocol restrictions prevent unexpected network reads during
native inspection/export; they are not a sandbox for hostile media files.

Browser takes accumulate in memory before saving; use native capture for long
sessions. Clearing browser storage can delete projects. Native webcam capture
is an overlay, not an independent camera-video recording track. Experimental
AI/chat providers and real streaming accounts need separate validation.

See [the 0.7.2 review](docs/SECURITY-REVIEW-0.7.2.md) for tested behavior and open
release checks. No guarantee of an exhaustive audit is implied.

## Reporting

For a suspected vulnerability, use GitHub's **Report a vulnerability** on this
repository's Security page if available. Do not post secrets, recordings, or a
working exploit in a public issue. If private reporting is unavailable, open a
minimal issue asking the maintainer for a private reporting channel. Include
version/environment details privately and rotate any exposed credentials.
