# OMA-BS 0.7.4 — explicit destination enable and save

The previous button displayed its current state (Enabled/Disabled) but inverted
that state when pressed. It was easy to interpret Enabled as an enable action
and save a disabled channel. The resulting stream error also incorrectly implied
that no destination had been saved.

- Separate Enable & save / Disable & save actions set an explicit boolean and
  persist it immediately. Repeating Enable & save keeps the channel enabled.
  Existing URL/key drafts are included in that explicit save. Other channels'
  enable states are preserved.
- The save helper reads back the file used by stream start and verifies it
  matches before confirming success. It returns enabled and ready counts without
  returning credentials.
- Save feedback distinguishes ready destinations, missing credentials, and all
  destinations disabled. Start errors distinguish absent from disabled profiles.
- No destination is automatically enabled by installation or migration, and
  saving/enabling does not begin a broadcast.

Validation: eight profile tests, including enable → save → native stream-read,
repeated enable, disabled/incomplete cases, readback mismatch, key redaction and
file permissions; updater checks, QML syntax and the Omarchy validator. Physical
mouse interaction and Twitch broadcast playback require device confirmation.

After updating and restarting the shell, open Stream and press Enable & save on
the Twitch card. Wait for Saved and verified: 1 destination(s) ready, then press
Stream beside Record. All earlier 0.7.2 security and 0.7.3 keyboard fixes remain.
