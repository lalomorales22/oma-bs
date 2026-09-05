# OMA-BS 0.7.3 — native text entry

The native Stream URL and key fields could look available but receive no keyboard
input. The widget used PopupCard (an xdg popup) attached to Omarchy's bar, whose
keyboard focus is explicitly disabled. Omarchy provides KeyboardPanel for panels
with keyboard interaction; OMA-BS now uses it with an internal focus target.

- Native text fields use a keyboard-capable panel surface. This also covers
  gallery search and editor fields.
- Stream URL/key changes update the draft immediately while typing or pasting;
  saving does not depend on a later focus-loss event.
- Stream keys remain masked and sensitive input disables predictive suggestions.
- Escape dismisses the panel through its existing close action. Omarchy's
  KeyboardPanel handles outside-click dismissal and releases focus on close.

Validation: QML syntax, actual Omarchy plugin validator, private streaming-profile
round trips, and updater backup/migration/rollback checks. A live Hyprland session
is unavailable in the build environment, so compositor behavior needs device
confirmation. The browser studio is unchanged from 0.7.2.

On the device: finish capture/export, install the archive, restart the shell,
open Stream, add/select a destination, type or paste its RTMP(S) ingest URL and
key, then Save destinations. Reopen the panel to check the saved values; do not
post keys in screenshots or logs. Start streaming from the oval Stream button.

This includes the earlier [security repairs](CHANGELOG-0.7.2.md).
