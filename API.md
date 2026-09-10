# Owner API v0.2

All operations use JSON POST requests to the application's configured origin, not directly to MikroTik. Send `Content-Type: application/json`, `X-App-Token: <private launch token>` and the exact `Origin` shown by the launch URL. HTTPS is mandatory for non-loopback access. Never embed a router password or permanent owner token in a mobile build.

| Endpoint | Request | Result / behavior |
|---|---|---|
| `/api/status` | `{}` | Fresh router snapshot, sanitized users/sessions, clock verification, observed timestamp and counts |
| `/api/ticket/action` | `{"id":"*A","action":"disable","confirmation":"DISABLE"}` | Disable the local account and revoke sessions/cookies; also supports `disconnect` / `DISCONNECT` and `enable` / `ENABLE` |
| `/api/expiry/preview` | `{}` | Reviewable scheduler operations and first-login hook source |
| `/api/expiry/install` | `{"confirmation":"INSTALL"}` | Add the versioned router scheduler, or return count 0 when already installed identically |
| `/api/vouchers` | See below | Create a batch and its dedicated tracked profile |
| `/api/history` | `{}` | Change records for the connected router; action records can have partial/uncertain outcomes |
| `/api/demo/activity` | `{}` | In demonstration mode only, add sample active and expired tickets |

Example tracked-voucher request:

```json
{
  "profile": "ns-nelsonict-users",
  "server": "hotspot1",
  "count": 10,
  "duration": "1d",
  "expiry_mode": "startup",
  "utc_offset": 60,
  "closing_time": "23:59",
  "fallback_time": "10:10",
  "confirmation": "CREATE"
}
```

`expiry_mode`: `elapsed`, `business`, `startup`, `connected`, `fixed`. Fixed mode also requires `fixed_at`, for example `2026-12-31T22:00:00+01:00`; it must be future and within 366 days. `duration` supports `1d`, `3d`, `1w`, `28d` and is used by elapsed/connected modes. Omitting `expiry_mode` retains the v0.1 connected-time creation behavior, without first-login hooks.

User status adds:

- `first_login`: router-recorded epoch seconds or null; never backfilled from session uptime.
- `current_session_started`: estimate from snapshot time minus the longest current session uptime, or null.
- `expires_at`: computed/recorded epoch deadline or null.
- `policy`: managed mode or `legacy`.
- `expiry_state`: `expired`, `valid`, `unused`, `first-login-unrecorded`, `clock-unverified`, `invalid-policy`, `legacy-unknown`.
- `overdue_active`: true when the ticket is definitely expired and still has sessions.
- `session_count`: number of active sessions for that local account.

`counts.connected_users` counts distinct usernames across all active sessions; `counts.sessions` counts sessions. `observed_at` is the management server's snapshot time; `clock` separately reports router time verification. Do not equate device count with unique people.

Disable and disconnect may partially succeed; consult history before retrying. A disable retry is allowed even when the account is already disabled, so remaining sessions/cookies can be cleaned up. Enable refuses expired, invalid-policy and clock-unverified managed tickets. A valid ticket can log in again after disconnect.

The current token gives one trusted owner full access, and all clients share one router connection. Native-app account roles, revocable per-device pairing and cloud relay remain future work.

## v0.3 templates and credentials

See [TEMPLATES.md](TEMPLATES.md) for template routes, portal activation and credential-format fields. Separate usernames/passwords are returned only for newly generated batches; templates contain no ticket secrets.

## LAN connection and direct portal installation (v0.4)

`POST /api/connect` accepts `host`, `username`, `password`, optional `transport` (`api`, `api-ssl`, `http`, `https`), optional `port`, and optional TLS `fingerprint`. Omitted transport retains HTTPS for existing clients; the new UI selects API by default. Omitted port follows the chosen service. Status includes transport. Plain transports are limited to private IPv4 LAN addresses.

`POST /api/portal/prepare` accepts `server` and a validated `template`, returning a ten-minute, connection-bound plan. `POST /api/portal/deploy` accepts `plan_id` and `confirmation: "INSTALL PORTAL"`. Plans are consumed before writing. The result includes `journal` and `directory`. A portal-deploy journal restores only the profile activation; copied/uploaded files are retained. Existing manual portal endpoints remain available.

## Profile prices

`POST /api/profiles/prices` lists existing user profiles with `id`, `name` and optional `price` (`amount`, `currency`, `label`). `POST /api/profiles/price` accepts matching `id` and `name`, decimal-string `amount` (0–999999999.99; at most two decimals), and uppercase three-letter `currency`. Empty amount removes the saved price. These routes require the normal owner token and a router connection.

New vouchers include `base_profile` and, when priced, `price_amount`, `currency`, and `price_label`. The price is copied server-side from the selected base profile and takes precedence over the template price during rendering. Prices are stored on the backend, not in router credentials or expiry comments.

## Voucher history and reprinting

Owner-authenticated endpoints require a connected router. `POST /api/vouchers/history` returns batch summaries without credentials. `POST /api/vouchers/reprint` accepts `batch` and/or `profile`, plus nonnegative `offset`, and returns up to 100 confirmed vouchers, `total`, `offset` and `demo`. Filters intersect when both are supplied. Profile matches original base or generated router profile.

`POST /api/vouchers/import` recovers readable credentials from existing Nelsonict-marked router accounts and returns added/skipped counts. Imported prices are deliberately blank; timestamps represent recovery time. It does not write to the router. No endpoint creates accounts during preview/reprint.

## Saved router locations

Owner-authenticated routes available before router connection: `/api/locations/list` returns metadata; `/api/locations/save` accepts `name`, `host`, `username`, `transport`, optional `port` and `fingerprint`, plus an existing `id` for updates; `/api/locations/delete` accepts `id` and refuses deletion of the active location. Password fields are discarded during save. Up to 100 locations are supported.

`/api/connect` accepts `location_id` and `password` to load saved settings on the server. Status includes `location_id` and `location_name`. Switching clears pending plans; one backend connection is shared by all owner clients. Saved-location archives/prices are scoped by location ID and router identity. Manual connections retain their previous storage scope. Change history and rollback verify the location ID as well as router context.

## Payments and backups

All endpoints retain owner token/Origin checks; none are public customer APIs.

- `POST /api/payments/create`: customer `email` plus voucher settings; amount is loaded server-side from the saved profile price. Returns reference, checkout URL and mode. Creates exactly one ticket entitlement.
- `POST /api/payments/list`: order summaries for the active location, including state and issued batch.
- `POST /api/payments/check`: verify eligible pending orders and attempt issuance; background processing also runs while the backend remains connected.
- `POST /api/backup/export`: returns the application backup JSON.
- `POST /api/backup/preview`: accepts `backup`, validates and reports file/replacement counts.
- `POST /api/backup/restore`: accepts `backup` and `confirmation: RESTORE`; requires a disconnected router. Returns restored count and recovery filename.

See PAYMENTS.md and BACKUPS.md for scope and limitations. Restore endpoints accept larger bounded requests; other API limits remain unchanged.
