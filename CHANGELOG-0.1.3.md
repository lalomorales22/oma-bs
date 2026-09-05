# OMA-BS 0.1.3 — npm runtime migration

Fixes installation/update validation after Studio has been opened. Earlier
launchers ran npm inside the plugin, generating .bin symlinks that Omarchy rejects.

## Changes

- Writable Studio source and npm dependencies now live in
  `${XDG_DATA_HOME:-~/.local/share}/oma-bs/studio`.
- The updater relocates installed dependencies before validating the target.
  Existing runtime dependencies, if present, are preserved in a separate backup.
- Source updates and dependency moves are rolled back on validation failure.
- The launcher copies source out of the plugin before running npm/Vite, and never
  puts a node_modules symlink back into the plugin.
- It gracefully stops only recognizable same-user OMA-BS Vite processes during
  migration. It does not kill unrelated Node processes or force-stop recordings.
- Vite uses strict port 4173, retaining the browser origin used by previous
  versions and refusing to silently choose another port.
- Includes the branding and camera-control repairs from 0.1.2.

## Updating

Stop recording and close the Studio tab. Extract this release into a fresh
Downloads directory and run `python3 oma-bs/scripts/update-local`. Leave the
existing plugin and old backups where they are; the updater migrates them.

Open Studio after installation. Dependency installation should not be necessary
when the existing Vite installation is complete. Logs are now at
`~/.local/share/oma-bs/studio.log` (or under XDG_DATA_HOME when configured).

## Verification

Regression tests reproduce an npm-style symlink, confirm the real upstream
Omarchy validator rejects the original plugin tree, migrate dependencies, then
confirm validation succeeds. Additional tests cover preserving existing runtime
dependencies, source-copy exclusions, updater ordering, and rollback.

Host Quickshell, physical capture, and browser runtime validation remain separate
checks; development tests do not establish those behaviors.
