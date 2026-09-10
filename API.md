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
