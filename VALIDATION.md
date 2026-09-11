# Validation record

- 135 Python unit and local HTTP integration tests passed.
- Python compilation checks passed.
- Frontend JavaScript syntax check passed.
- HTTP tests exercised demo connect, plan, apply, voucher creation, user disable, rollback, disconnect, and rejection without an access token or Origin header.
- Browser visual/interaction QA was attempted but could not run because the runtime has no installed Chromium executable. No visual QA pass is claimed.
- No real RouterOS device was accessible. No RouterOS 7.24.2 certification is claimed.
- Windows/macOS execution is unverified. Previous remote CI attempts failed before test steps started; local results are independent of GitHub Actions.

Run `python3 -m unittest -v test_core test_http test_expiry test_mobile test_templates test_lan test_pricing test_voucher_history test_locations test_business test_gateways test_sales` from the project root. See ACCEPTANCE.md for the hardware release gate.

## v0.2 scope

New tests cover policy calculations, NTP gating, same/later-day startup, stable-power fallback, unused/fixed tickets, persisted deadlines, unknown legacy activation, tracked-profile creation, scheduler drift protection, expired-active counts, disable/disconnect and protected enable. They execute Python and simulated REST behavior, not RouterOS scripts.

Mobile transport tests also verified a real local HTTPS request with certificate validation, rejection of a foreign Origin, rejection of public/wildcard binds and rejection of plaintext LAN startup. No physical phone/browser UI pass is claimed.

## v0.3

20 additional tests passed for templates, credential formats, portal packages, installation/restore guards, and generated JavaScript authentication mapping. The latter use a mock DOM and hash callback, not a live RouterOS CHAP exchange. Physical browser/printer/router validation remains outstanding.

## v0.4

17 additional tests cover fragmented binary API frames, UTF-8, reply limits, sanitized traps, modern login ordering, TLS pin rejection before credentials, command/query mapping, private-address constraints and HTTP request construction. They use mocked sockets/connections rather than RouterOS hardware. Installer tests cover simulated copy/upload/readback/activation/restore, persistent-folder selection, occupied destinations, stale source metadata, failed copy, failed readback and profile drift. All 85 tests and Python/JavaScript syntax checks passed locally.

Hardware acceptance remains required for native `file/copy` command arguments and support, file permissions and content editing, API-SSL certificates, real captive login and reboot persistence. No browser visual pass is claimed.

## Profile pricing

Eight added tests cover decimal validation, zero/removal, router-scoped persistence, demo isolation, frozen batch prices, tracked-profile inheritance and escaped printing. All 93 local tests passed. No real browser/printer test is claimed.

## Voucher history

Eight additional tests validate batch/profile selection, credential retention, pagination, partial writes, archive failures before router mutation, persistent router isolation, legacy recovery without guessed credentials/prices and demo reset. All 101 local tests passed. Browser/printer and real-router recovery acceptance remain outstanding.

## Account table controls

Local JavaScript checks passed for combined filters, case-insensitive search, natural username sorting, duration and unlimited-allowance sorting, empty results and source-data preservation. Frontend syntax checks and all 101 Python tests passed. Browser visual/keyboard acceptance is still pending.

## Saved locations

Five added tests cover password-free persistence, rename/removal, connection validation, use of server-side saved settings, plan invalidation and isolation of prices/archives for sites with identical LAN IPs and router identities. All 106 tests passed locally; frontend syntax checks passed. Physical multi-site and browser interaction testing remain outstanding.

## Payments and backups

Twelve tests cover mocked provider verification and duplicate prevention, mismatches, pending/network failures, uncertain issuance, initialization intent, backup roundtrip/recovery, invalid paths/data, write rollback and payment-ledger exclusion. All 118 local tests passed, including end-to-end application routes for a mocked paid order, archived price snapshot and restore connection guards. No real Paystack transaction, hardware payment issuance, browser visual pass or power-loss restore test is claimed.


## Additional payment providers

Seven mocked tests cover Flutterwave/Monnify initialization, verification and amount conversion, sandbox authentication, transaction references, invalid URLs/modes, merchant-key changes and duplicate prevention. All 125 local tests passed. Provider sandbox, live transactions and real-router issuance remain unverified.

## SQLite sales reports

Ten added tests cover sold/unsold transitions, duplicate protection, retained correction records, daily/monthly grouping and timezone boundaries, currency separation, verified payment indexing, test/pending exclusions, location isolation, frozen prices, unpriced/partial vouchers, SQLite persistence, backup/restore validation, filter validation, pagination and owner demo routes. All 135 tests passed locally, with frontend syntax checks. Browser visual testing and real merchant transaction reconciliation remain outstanding.
