# Release checklist

## Local gates

```bash
python3 -m unittest discover -s tests -v
node --test tests/*.test.mjs
omarchy plugin validate .
```

Run browser dependency checks in a separate source copy outside the installed
plugin tree: `npm ci`, `npm run typecheck`, `npm test`, and `npm run build`.
The root GitHub workflow does this automatically in an external runtime copy.
QML syntax must parse, but syntax and unit tests cannot replace a real shell run.

## Real Omarchy device — before publication

- [ ] Record Omarchy/Quickshell, GPU/driver, GPU Screen Recorder, FFmpeg, and Qt
      versions in the release notes; this targets Quattro, not the old Waybar API.
- [ ] Save edits, finish captures/exports, close the browser studio, and stop any
      manually launched browser relay before updating. Restart the shell after.
- [ ] Confirm **OMA-BS · 0.7.1**, five dock tabs, visible footer, and oval
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

Review the included MIT license and ownership notices. Choose the public repo
name `lalomorales22/oma-bs` or update README/submission URLs to the final name.
Create an empty repository, then from the reviewed source folder:

```bash
git init -b main  # only for an extracted archive without .git
git add .
git commit -m "Release OMA-BS 0.7.1"
git remote add origin https://github.com/lalomorales22/oma-bs.git
git push -u origin main
```

For an existing checkout, use its current branch/history and remote instead.
Never stage private runtime/config files, dependency trees, recordings, or keys.
Wait for CI, add a real redacted screenshot, then create tag `v0.7.1` and a GitHub
release with CHANGELOG-0.7.1.md. Source archives need prefix `oma-bs/` and must
exclude node_modules, caches, and internal symlinks. Validate the extracted copy.

## Marketplace

Submit the prepared [issue draft](MARKETPLACE-SUBMISSION.md) after the repository
is public and the device checklist passes. Review the current form and wait for
maintainer approval. Preparing this file does not publish or submit anything.
