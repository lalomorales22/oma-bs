# OMA-BS Studio v0.7.6

Record, stream, browse, and edit from the Omarchy Quattro bar.

## Included

- Display, window, and region recording with desktop audio, microphone, or both.
- Webcam overlay, separate audio sources, and a native video/image/audio gallery.
- Basic layered editing with an optional advanced browser studio.
- Multiple RTMP/RTMPS destinations, independent streaming controls, and a local
  recording backup that continues when a destination fails.

## Streaming repair

This release fixes the empty publishing name observed with FFmpeg 9.0.1. Both
the native widget and browser studio now pass private connection settings
directly to FFmpeg's streaming library through a small compiled transport worker.
Stream keys stay out of process arguments and raw logs. RTMPS verifies server
certificates.

## Verified

- The maintainer confirmed a successful Twitch broadcast and the subsequent
  stop-streaming/save-recording flow on an Omarchy device.
- The maintainer confirmed that the fresh-install check passed.
- GitHub Actions passed for commit
  `3624ec822f76a66ff153b458ed18bab77f84b03d`.
- Local verification: 66 Python tests passed, one environment-dependent test
  skipped, and four Node tests passed. Omarchy plugin validation passed.
- Streaming tests inspect actual RTMP application/publishing fields, audio/video
  delivery, destination failure isolation, and rejection of untrusted TLS
  certificates.

The optional browser streaming path and multiple destinations are covered by
local integration tests. Other streaming platforms have not been confirmed on
real accounts. Marketplace listing has not yet been approved.

## Install

Requires Omarchy Quattro. Install the streaming build dependency, then the plugin:

```bash
sudo pacman -S --needed gcc ffmpeg
omarchy plugin add https://github.com/lalomorales22/oma-bs.git --enable
```

The small sender builds against the installed FFmpeg libraries and is cached
outside the plugin folder. See the README for optional inline playback and
browser studio dependencies, configuration, and safe removal.

For an existing archive installation, extract the release separately and run
`python3 oma-bs/scripts/update-local`. Finish recordings and close the browser
studio before updating; restart the Omarchy shell afterward.

Source and security notes: https://github.com/lalomorales22/oma-bs
