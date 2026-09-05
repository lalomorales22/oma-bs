# Prepared marketplace submission

Status: draft, not submitted. Public v0.7.6 passed GitHub Actions. The maintainer
has confirmed Twitch streaming and the fresh-install check on his device.
Three real screenshots are included in the README. The GitHub release is
prepared for publication using `scripts/publish-release` from its release kit. See
[RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md) for the verification scope.

The official route is the marketplace's **Submit plugin issue form**, followed
by automated validation of the public repository and maintainer review. It is
not a pull request to the main Omarchy operating-system repository.

- [Publishing guide](https://plugins.omarchy.org/publish.html)
- [Submission form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml)

## Form fields

**Repository URL:** `https://github.com/lalomorales22/oma-bs`

**Category:** Productivity

**Tags:** Bar, Media, Quickshell

**Maintainer notes:**

OMA-BS (Omarchy Broadcast Studio) is a native Quattro bar widget for screen,
window, and region capture; desktop/microphone audio; a dismissible webcam
overlay; an inline video/image/audio gallery; basic layered editing; and
multi-destination RTMP(S) streaming. The optional browser studio provides
additional editing and scene tools adapted from my Chroma Canvas application.

The root manifest declares `lalo.oma-bs`, version `0.7.6`, kind `bar-widget`,
entry point `BarWidget.qml`, default section `right`. Native capture depends on
the installed Omarchy helpers, GPU Screen Recorder, FFmpeg/ffprobe, and mpv.
Qt Multimedia is optional for inline playback. The browser studio additionally
requires Node.js/npm and installs npm dependencies outside the plugin folder.
Streaming builds a small C sender using gcc and the headers included in Arch's
FFmpeg package. The executable is cached outside the plugin under
`~/.cache/oma-bs/transport`; no binary or downloaded dependency is bundled.

This plugin runs local processes with the user's privileges. Native captures and
exports remain in the user's media folders. Explicitly pressing Stream sends
the selected capture and mixed audio to saved enabled destinations and keeps a
local backup. Merely saving destinations does not start streaming. Native keys
are local plaintext with owner-only file permissions; temporary connection files
keep credentials out of process arguments. The optional browser relay listens
only on loopback; LAN phone-camera mode is a separate explicit developer option.

There are no automatic system-package installers or install hooks. Omarchy
manages its own plugin registration. Runtime, dependency, and update-backup
locations and safe removal are documented in README. System audio defaults are
not changed. The source archive contains no node_modules or internal symlinks.

Known limits: single-window capture does not include the separate native webcam
overlay; native editor compositions are not live capture scenes; an ordinary
recording must end before a stream can start. Provider account access and real
dashboard validation are required; automated streaming tests target localhost.

## Submission confirmations

Review these against the live form; do not pre-check pending work:

- [ ] Public repository has working install and removal instructions.
- [ ] MIT license and third-party dependency/attribution notices reviewed by owner.
- [ ] Owner has permission to distribute all code and included assets.
- [ ] Plugin does not overwrite unrelated user configuration without consent.
- [ ] Understand that marketplace approval is not a security audit.
- [ ] Attach a real screenshot of the widget, editor, and Stream tab if desired;
      hide all stream keys and account-specific ingest URLs.

The September 5 review maps the current guide and issue form to repository files
in [SECURITY-REVIEW-0.7.2.md](SECURITY-REVIEW-0.7.2.md). Owner confirmations and
real-device checks remain explicit; no marketplace approval is claimed.
