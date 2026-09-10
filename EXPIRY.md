# Ticket expiry and first-login records

The implementation is ready for lab testing, not hardware-certified. Read ACCEPTANCE.md before enabling it on a customer router.

## Enable tracked tickets

1. Configure router NTP and verify its status is `synchronized` in WinBox.
2. Connect the application and open **Vouchers & users → Review / install engine**.
3. Review the scheduler and login-hook source, preserve a router backup, then enter `INSTALL` to add the scheduler.
4. Select a plain existing user profile, package duration where applicable, expiry mode and location settings. Confirm ticket creation.
5. The batch receives a dedicated profile containing the login hook. Existing profiles and custom scripts are not overwritten. Source profiles with custom login/logout automation are rejected.

The scheduler is named `ns-expiry-v2`, runs every **30 seconds**, and uses `read,write` permissions. Router account/script permissions must allow the indicated operations. If RouterOS rejects them, inspect the returned operation and policy in WinBox; the app does not elevate permissions or disable permission checks.

New user comments use a versioned `ns2,` record containing policy, package duration, location offset, closing/fallback times, activation timestamp, deadline and batch ID. These fields persist on the router. Do not manually edit machine-owned comments. Save backups and test persistence across power cycles on the target device.

## Policies

| Mode | Start | Expiry |
|---|---|---|
| Elapsed | First login with synchronized NTP | First login + 1d, 3d, 7d or 28d, counting offline time |
| Business day | First login | Next configured closing time after activation; login exactly at closing gets the next day's closing |
| Next-day startup | First login | On a later local calendar day, boot + 600 seconds; if continuously powered overnight, next-day fallback closing time |
| Connected | Actual accumulated online usage | RouterOS `limit-uptime`; offline time does not count |
| Fixed | Configured absolute instant | Explicit date/time with UTC offset, including unused tickets |

Business/startup modes are daily policies; the duration selector is disabled. Different batches at the same hotspot can use different policies. Location UTC offset is stored per batch, in minutes: Nigeria is +60. Fixed-offset scheduling does not automatically follow daylight saving. Choose elapsed/fixed-instant validity or deliberately issue batches with the correct local offset when daylight saving matters.

### Startup behavior

- Same-day reboot does not make an activated ticket expire.
- A used ticket first evaluated on a later local day calculates router boot time as synchronized epoch time minus uptime.
- A later-day boot yields boot + 10 minutes. NTP arriving 20 minutes after boot does not add a new grace period: the already-due ticket is disabled on that synchronized evaluation.
- With no later-day reboot, the next-day fallback time applies. The default is 10:10 local time and is configurable.
- Once a due date is written, it is never moved later by a further reboot. For example, a fallback deadline recorded after midnight remains the deadline even if the router subsequently restarts. This prevents reboot-based extensions.
- Unused startup tickets remain unused and do not expire just because a day passes.
- After several days powered off, a used ticket without a previously recorded deadline gets 10 minutes from the next synchronized later-day boot. A ticket with an already recorded past deadline expires as soon as checked.

The 30-second scheduler interval means cutoff enforcement can occur up to approximately 30 seconds after the deadline, plus router processing time. Login hooks also evaluate deadlines at login. This is not a guarantee of second-exact service cutoff on every device.

## Time, records and failure behavior

- Only the login hook writes first activation; periodic polling does not fabricate historical first login.
- A new tracked login with unverified NTP is disconnected and its cookies removed, for every mode, so no first-login timestamp is invented. Periodic checks also disconnect active managed calendar sessions while time remains unverified. The account is not permanently disabled merely because NTP is unavailable.
- Already active connected-time sessions can continue without NTP; their accumulated-use limit still applies. New tracked logins wait for synchronization. Before issuing tickets the app also requires synchronized NTP.
- Known elapsed/fixed deadlines are durable; accounts are not automatically re-enabled after a backward clock adjustment. The dashboard reports clock-unverified when recorded activation is in the future relative to the router.
- Expiry disables accounts and removes sessions/cookies while retaining user and policy records.
- Malformed policy/script errors are logged on the router and the relevant managed session/cookies are removed; inspect the log and comment. The dashboard flags malformed metadata.
- The app refuses to remove the scheduler through its rollback control while managed tickets still exist. Disabling/deleting the scheduler or altering hooks through WinBox can still break enforcement; inspect automation as part of acceptance/operations.
- The Python demo/evaluator tests exercise policy arithmetic and API behavior. They do not execute RouterOS scripts or prove their behavior on real firmware.

## Older tickets

Older or externally created local accounts show unknown historical first login. The app can still count active sessions, display the current session's estimated start and flag an exhausted connected-time allowance. It does not guess calendar expiry for accounts without managed policy metadata. Such accounts can be disabled or disconnected explicitly. For calendar policies and first-login tracking, issue new tracked tickets; automatic migration of already-used accounts is not included.
