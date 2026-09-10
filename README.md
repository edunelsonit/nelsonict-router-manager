# Nelsonict Router Manager

A local MikroTik management application for **Nelsonict Services Limited**: connect a router, inspect its configuration, review a setup plan, apply additions, and create printable hotspot vouchers.

**Version 0.2.0 — pilot, not a production-certified release.** Targets the RouterOS v7 REST interface. RouterOS **7.24.2 is the requested compatibility target and has not been verified on hardware**. The official changelog page available during development did not establish that exact release. No real router was connected during development.

## Run it

Requires **Python 3.11 or newer** and a current desktop browser. No pip or npm packages are required to run the app.

### Windows

1. Install Python from [python.org](https://www.python.org/downloads/) with the Python launcher.
2. Extract this project into a writable folder.
3. Double-click `start-windows.bat`, or run `py -3 server.py` from that folder.
4. Keep the terminal window open. The browser opens automatically.

### Ubuntu / Linux / macOS

Open a terminal in the project folder:

```sh
python3 server.py
```

If Python is unavailable, install Python 3.11+ using your platform's normal installer. `sh start-unix.sh` is also provided.

By default the app listens at **127.0.0.1:8765 only**. Optional HTTPS LAN/VPN mode supports phone browsers; see [MOBILE.md](MOBILE.md). Open the private launch URL printed in the terminal if the browser does not open. Its fragment contains a per-process access token. Do not share it. Stop the app with Ctrl+C; stop/restart it to invalidate the token. Use `python3 server.py --port 8766` if the default port is occupied.

Click **Open demonstration** to explore without touching any router. All demonstration records are simulated and disappear when you stop or reset that mode.

## Why this stack

- **Python backend:** cross-platform networking, certificate verification, input validation and operation journaling, with no installation dependency chain.
- **HTML, CSS and JavaScript:** a responsive browser interface without a build step or external CDNs.
- **RouterOS HTTPS REST API:** authenticated JSON operations instead of injecting user input into RouterOS scripts.
- **Local execution:** your router's private IP is reachable from your LAN or management VPN. A publicly hosted web page or GitHub Pages cannot replace this backend.

This is a desktop-hosted, single-owner application with a mobile web interface. Owners can access it through optional HTTPS on a trusted LAN or VPN. It is not a native Android/iOS app or multi-tenant SaaS. All authorized owner devices share one active router connection.

## First router connection: WinBox walkthrough

An IP alone cannot enable or authorize management. Complete this once through a trusted WinBox session.

1. **Keep an independent management path.** Your computer must use the existing management LAN, never the spare port you intend to configure. Arrange local/physical recovery access.
2. **Save a backup.** In WinBox, open Files → Backup and download the resulting file. Also export the current configuration from Terminal using `/export file=before-nelsonict` and download the `.rsc` file. Protect backups because they may contain sensitive information. This application does not create or restore full backups automatically.
3. **Prepare a TLS server certificate.** In System → Certificates, import or create a certificate suitable for HTTPS service. Prefer a trusted certificate with the router IP in its subject alternative names. For a self-signed certificate, export only its public certificate using WinBox over the trusted connection.
4. **Obtain its fingerprint.** On a computer with OpenSSL installed, run:

   ```sh
   openssl x509 -in router.crt -noout -fingerprint -sha256
   ```

   Copy the hex fingerprint after `=`. Use the certificate actually assigned to `www-ssl`. Never accept a fingerprint supplied only through an untrusted network connection. The app verifies a provided pin before sending credentials.
5. **Enable HTTPS management.** In IP → Services, open `www-ssl`, set the certificate and HTTPS port, enable it and restrict Available From to your management computer's `/32` address or a trusted management VPN subnet. Verify the existing firewall allows this management access. Do not expose management to the public internet.
6. **Create an application account.** In System → Users → Groups, create a dedicated group with `read,write,rest-api`; then create a password-protected user in that group. Your RouterOS policy and device-mode must permit the requested features. Additional broad policies are not added by this app. RouterOS write permission is powerful; restrict the account's allowed source address too.
7. **Connect in the app.** Enter router IP, HTTPS port, username and password. Add the verified fingerprint only when using the pinning option. Without a pin, normal OS CA and IP/hostname verification is mandatory.
8. **Inspect the detected version and interfaces.** Build a plan in the Setup wizard. Read all warnings and exact operations before confirming.

The router password is not persisted in configuration, browser storage, or journals. It remains in process memory for the active connection. Disconnect and stop the process when finished. Other users or malware with access to the same OS account remain outside this pilot's security boundary.

## Supported scenarios

| Scenario | What is created | Prerequisites |
|---|---|---|
| Existing hotspot | A named local-user profile with upload/download limits and one simultaneous login | Enabled hotspot already configured and working |
| New paid hotspot | Gateway, DHCP pool/network/server, IPv4 input and forwarding rules, NAT, hotspot server/profile and voucher profile | Unused Ethernet port; working WAN; verified WAN firewall; global IPv6 disabled; FastTrack disabled; device-mode permits Hotspot; default hotspot files present |
| Office internet | Gateway, DHCP pool/network/server, IPv4 input and forwarding rules and NAT | Unused Ethernet port; working WAN; verified WAN firewall; global IPv6 disabled |

The new network is internet-only: forwarding toward RFC1918 and link-local destinations is blocked. Attach an external access point in AP/bridge mode to the spare port. Set wireless client isolation on that AP if clients must not communicate with each other; this application does not manage external APs or same-segment Layer 2 traffic.

**These are additive LAN scenarios, not factory-reset or full WAN installers.** The wizard never detaches a port from an existing bridge, changes a WAN, upgrades packages, changes global IPv6 settings, or resets the router. It refuses occupied ports and overlapping interface, DHCP-network and address-pool ranges. Existing firewall customizations can still conflict with the generated plan: review the exact operation list. A drop rule's presence is only a preliminary check, not a security audit.

Hotspot setup uses RouterOS default portal assets and `http-chap,cookie`, with local users and RADIUS disabled for the newly created profile. Branded one-field login, HTTPS captive portal certificate provisioning and file uploads are future work. For an existing hotspot, inspect its existing login methods and FastTrack exclusions yourself. Profile rate limits can be bypassed by unsuitable FastTrack configuration.

## Owner dashboard and mobile access

See connected users and sessions, first login for tracked tickets, expiry dates, and **expired but still connected** alerts. Search/filter accounts and disable, disconnect or re-enable valid tickets. The view refreshes every 15 seconds while visible and marks failed polls as stale. Older accounts without activation metadata show unknown first login.

The mobile web dashboard uses the same backend. See [MOBILE.md](MOBILE.md) for HTTPS LAN/VPN startup, certificate and token handling. See [API.md](API.md) for the future mobile-client contract.

## Vouchers and configurable expiry

1. Open Vouchers & users and review/install the router expiry checker with NTP synchronized.
2. Select an existing plain user profile and hotspot server.
3. Choose **elapsed**, **business-day closing**, **next-day startup**, **connected-time**, or **fixed date/time** expiry. Elapsed/connected modes support 1d, 3d, 7d and 28d. Daily policies have location and closing/fallback controls.
4. Confirm creation of 1–100 random 10-digit PINs. Each batch receives a dedicated profile with the first-login hook; existing custom hooks are not overwritten.
5. Print or export CSV. On the standard RouterOS page, enter the PIN in both username and password fields.
6. Inspect the owner dashboard. Expiry disables accounts and removes active sessions/cookies while keeping account records. Owner controls work on any local hotspot account, including older tickets.

The scheduler and activation record live on the router so enforcement does not depend on the management app staying open. **Native scripts still require real-router acceptance testing.** The checker runs every 30 seconds; this is not a second-exact cutoff guarantee. Location scheduling uses an explicit fixed UTC offset (Nigeria +60 minutes), without automatic daylight-saving changes. See [EXPIRY.md](EXPIRY.md) for exact policies and clock/power-loss behavior.

Legacy API callers that omit `expiry_mode` retain connected-time-only behavior. Historical first-login timestamps cannot be recovered for older accounts. No automatic migration guesses those dates. Do not manually edit managed `ns2,` comments.

## Plan, apply and recovery

- Plan generation reads router configuration and performs scenario-specific checks.
- The plan lasts 10 minutes and binds to a configuration fingerprint. A changed configuration requires a new plan. No live lock exists on RouterOS; avoid concurrent WinBox edits while applying.
- Apply requires backup acknowledgment and the literal word `APPLY`.
- Every operation is journaled before sending. Successful create responses record the returned RouterOS object ID.
- A lost/error response is marked **uncertain** and stops subsequent writes. The app never automatically retries a write.
- Open Change history to inspect results. Rollback removes known additions in reverse order and stops if an object differs from the recorded creation values.
- Rollback is **not a transaction or RouterOS Safe Mode**. It cannot reverse uncertain writes, all side effects, arbitrary later modifications or a lost management connection. Inspect uncertain writes manually using their recorded menu and properties. On router reset/replacement, do not reuse old change records.
- Setup rollback can disconnect users. Rolling back a voucher batch deletes those users. Do not rollback a populated hotspot profile until dependent vouchers have been dealt with.

Local journals live in `data/`, with restrictive POSIX modes where supported. They contain router addresses and voucher identifiers (which are also PINs), so treat them as secrets. Windows users should keep the project in a private user folder with appropriate ACLs. `data/`, exports, backups, private keys and launch/runtime state are excluded from Git. The app only serves three fixed frontend assets; journals are never exposed as static files.

## Development and verification

```sh
python3 -m unittest -v test_core test_http test_expiry test_mobile
python3 -m py_compile core.py server.py expiry.py
node --check web/app.js
```

Node is optional and only needed for the JavaScript syntax check. GitHub Actions includes Python checks on Ubuntu and Windows. A successful simulation test does not establish MikroTik compatibility.

See [ACCEPTANCE.md](ACCEPTANCE.md) for real-router release gates and [ROADMAP.md](ROADMAP.md) for the broader product plan.

## Reference archive

The supplied `Mikhmon Server.zip` was inspected as a feature reference. Its `include/version.php` reports **3.20 06-30-2021**; it contains 98 PHP files, a RouterOS PHP API class, hotspot/user/profile management and voucher printing. The archive contains a GPL v2 license text. This project contains newly authored code and does not redistribute the supplied PHP code, server binaries, assets or configuration data. This repository uses the GPL-3.0 license selected when the repository was created; see [LICENSE](LICENSE).

## RouterOS references

- [REST API: HTTPS services, authentication and CRUD methods](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API)
- [Hotspot: IPv4, device-mode, profiles and user limits](https://help.mikrotik.com/docs/spaces/ROS/pages/56459266/HotSpot+-+Captive+portal)
- [Configuration backup/export and Safe Mode](https://help.mikrotik.com/docs/spaces/ROS/pages/328155/Configuration+Management)
- [Official downloads and changelogs](https://mikrotik.com/download/changelogs)

The linked legacy documentation warns that it is frozen; MikroTik directs readers to its [current manual](https://manual.mikrotik.com/docs/introduction/). Confirm behavior on the exact deployed version before business use.
