# Validation record

- 48 Python unit and local HTTP integration tests passed.
- Python compilation checks passed.
- Frontend JavaScript syntax check passed.
- HTTP tests exercised demo connect, plan, apply, voucher creation, user disable, rollback, disconnect, and rejection without an access token or Origin header.
- Browser visual/interaction QA was attempted but could not run because the runtime has no installed Chromium executable. No visual QA pass is claimed.
- No real RouterOS device was accessible. No RouterOS 7.24.2 certification is claimed.
- Windows/macOS execution and remote CI have not been run in this session.

Run `python3 -m unittest -v test_core test_http test_expiry test_mobile` from the project root. See ACCEPTANCE.md for the hardware release gate.

## v0.2 scope

New tests cover policy calculations, NTP gating, same/later-day startup, stable-power fallback, unused/fixed tickets, persisted deadlines, unknown legacy activation, tracked-profile creation, scheduler drift protection, expired-active counts, disable/disconnect and protected enable. They execute Python and simulated REST behavior, not RouterOS scripts.

Mobile transport tests also verified a real local HTTPS request with certificate validation, rejection of a foreign Origin, rejection of public/wildcard binds and rejection of plaintext LAN startup. No physical phone/browser UI pass is claimed.
