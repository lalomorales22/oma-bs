# Release checklist

## Confirmed on September 5, 2026

- The maintainer reports that Twitch broadcasting, ending the stream while
  retaining the local recording, and saving/playback passed on his device.
- The maintainer reports that the fresh-install check passed.
- Public v0.7.6 commit `3624ec822f76a66ff153b458ed18bab77f84b03d` passed
  [GitHub Actions](https://github.com/lalomorales22/oma-bs/actions/runs/33986733331).

The broader scenario checklist below is retained for future release testing;
these confirmations do not imply every capture mode or platform was tested.
The release notes are in [RELEASE-0.7.6.md](RELEASE-0.7.6.md).

## Local gates

Streaming tests need gcc and FFmpeg development headers. Arch's `ffmpeg` package
includes the headers; Debian/Ubuntu also need `libavformat-dev libavutil-dev`.
Run `python3 studio/stream_transport.py --check` to build/check the cached sender.

```bash
python3 -m unittest discover -s tests -v
node --test tests/*.test.mjs
omarchy plugin validate .
```

Run browser dependency checks in a separate source copy outside the installed
plugin tree: `npm ci`, `npm run typecheck`, `npm test`, and `npm run build`.
The root GitHub workflow does this automatically in an external runtime copy.
QML syntax must parse, but syntax and unit tests cannot replace a real shell run.

## Real Omarchy device — before marketplace submission

- [ ] Record Omarchy/Quickshell, GPU/driver, GPU Screen Recorder, FFmpeg, and Qt
      versions in the release notes; this targets Quattro, not the old Waybar API.
- [ ] Save edits, finish captures/exports, close the browser studio, and stop any
      manually launched browser relay before updating. Restart the shell after.
- [ ] Confirm **OMA-BS · 0.7.6**, five dock tabs, visible footer, and oval
      Stream button beside Record. Check the popup on a smaller/scaled display.
- [ ] Make a normal display, region, and window take. Test silent, desktop,
      microphone, and both inputs; inspect the saved MP4 and separate audio.
- [ ] Cancel the portal picker. Dismiss webcam during capture. Confirm webcam
      closes on stop and recorder exit. Use display/region for camera overlay;
      window-only mode intentionally excludes the separate webcam window.
- [ ] Save at least two enabled complete ingest destinations. Use private or
      unlisted broadcasts where supported; configure visibility in each service.
- [ ] Press Stream from idle and confirm screen, camera, and audio in each
      provider dashboard. Check synchronization, levels, resolution, and motion.
- [ ] End live: verify providers stop receiving while local recording continues.
      Start streaming again in the same take, then Stop both & save.
- [ ] Make one destination invalid or disconnect it. Check failed/partial state,
      unaffected destinations, continuing local backup, and clean manual restart.
- [ ] Confirm no keys in process arguments or capture logs; check `streaming.json`
      is mode 0600. Do not paste keys into an issue, screenshot, or CI log.
- [ ] Play the resulting gallery MP4 and each audio source; inspect `capture.ts`
      and `capture.mkv`. Check disk use on a longer take. Streaming retains both.
- [ ] Exercise inline gallery playback, crop/layers, preview, export, and saved
      editor reload. Native editor output does not change the live capture scene.
- [ ] Launch optional browser studio, import saved destinations explicitly, test
      a browser broadcast, stop it, and release camera/mic. Browser/native sessions
      have separate controls. Never assume one button stops the other engine.
- [ ] Clean-install in an isolated test account, enable, update, disable, remove,
      and reinstall. Confirm personal recordings/settings survive plugin removal.
- [ ] Review npm dependency audit and licenses before public release; document
      unresolved advisories and optional experimental service integrations.

## GitHub preparation

The public repository is `lalomorales22/oma-bs`. Its initial CI passed. The 0.7.6
archive includes a guarded publishing helper for the owner's authenticated `gh`:

```bash
python3 scripts/publish-review
```

It uses a fresh clone, requires the reviewed baseline tree, applies the bundled
patch, and pushes normally (never force-pushes). It stops if the repository has
changed. This helper is archive-only; regular checkouts use their usual Git flow.
Never stage private runtime/config files, dependency trees, recordings, or keys.
Wait for CI, add a real redacted screenshot, then create tag `v0.7.6` and a GitHub
release with CHANGELOG-0.7.6.md. Source archives need prefix `oma-bs/` and must
exclude node_modules, caches, and internal symlinks. Validate the extracted copy.

## Marketplace

Submit the prepared [issue draft](MARKETPLACE-SUBMISSION.md) after the repository
is public and the device checklist passes. Review the current form and wait for
maintainer approval. Preparing this file does not publish or submit anything.
