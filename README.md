# Nelsonict Router Manager

A local MikroTik management application for **Nelsonict Services Limited**: connect a router, inspect its configuration, review a setup plan, apply additions, and create printable hotspot vouchers.

**Version 0.4.0 — pilot, not a production-certified release.** Targets RouterOS v7 API and REST services. RouterOS **7.24.2 is the requested compatibility target and has not been verified on hardware**. The official changelog page available during development did not establish that exact release. No real router was connected during development.

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

## AI setup walkthrough

Open **AI walkthrough** to collect and download a setup snapshot, inspect an imported `.rsc`/JSON export, and preview supported bulk ticket repairs. Optional OpenAI analysis requires backend environment variables `OPENAI_API_KEY` and `OPENAI_MODEL`, plus explicit confirmation before sharing the projected evidence. Local checks and repairs work without AI.

Review and apply fixes for valid expiry comments, uptime limits, expired sessions and verified app-owned expiry automation. Select legacy tickets to preview and replace ordinary comments; managed expiry metadata stays protected. Missing activation dates require manual review. See [DIAGNOSTICS.md](DIAGNOSTICS.md) for configuration, supported repairs and limitations.

## Desktop packages

Open **Desktop packages** in the app for EXE/DEB build options. See [PACKAGING.md](PACKAGING.md) for local builds, GitHub artifacts and data migration.

## Why this stack

- **Python backend:** cross-platform networking, certificate verification, input validation and operation journaling, with no installation dependency chain.
- **HTML, CSS and JavaScript:** a responsive browser interface without a build step or external CDNs.
- **RouterOS API/API-SSL and HTTP/HTTPS REST:** structured commands with explicit transport selection.
- **Local execution:** your router's private IP is reachable from your LAN or management VPN. A publicly hosted web page or GitHub Pages cannot replace this backend.

This is a desktop-hosted, single-owner application with a mobile web interface. Owners can access it through optional HTTPS on a trusted LAN or VPN. It is not a native Android/iOS app or multi-tenant SaaS. All authorized owner devices share one active router connection.

## Saved hotspot locations

Open **Connect your router → Saved hotspot locations**. Enter a location name and the router IP, username, service, port and optional certificate fingerprint, then click **Save connection settings**. Select a saved location, enter its password and click **Connect & inspect**. Use New location for another site; update its display name with Save, or remove a disconnected saved location.

Passwords are session-only and must be supplied when connecting. Connection settings persist under `data/locations`. The application manages one active router at a time; all owner devices using this backend share that connection. Switching clears pending setup/portal plans. Your computer must have LAN or VPN access to the selected router; saving a remote address does not create connectivity.

Saved locations have separate profile prices, voucher archives and change history, including when sites use identical local IP addresses and router identity names. Existing data from manual connections remains under the original manual-connection scope: connect manually to access it. It is not automatically migrated to a saved location. Retain a saved location if you need its archived data; removing and recreating it assigns a new ID. Back up the complete `data` directory to preserve location settings and archives.

## First router connection over LAN

1. Connect the computer to the router's existing management LAN using Ethernet or Wi-Fi. A guest hotspot may require login or an explicitly permitted management path. Keep a backup and independent management access before changing network settings.
2. Enter the local router IP, username and password. The UI defaults to API on port 8728. Choose the router's enabled service; custom ports are supported.

| App selection | Router service | Default port | Account service policy |
|---|---|---|---|
| API | api | 8728 | api |
| API-SSL | api-ssl | 8729 | api |
| HTTP REST | www | 80 | rest-api |
| HTTPS REST | www-ssl | 443 | rest-api |

The account also needs read/write permissions. See EXPIRY.md for script installation permissions. The selected service must already be enabled and reachable through the firewall; an IP and password cannot turn on a disabled management service. Initial service configuration can use your existing trusted management tool. The app never changes service exposure or silently falls back to an unencrypted connection.

Plain API/HTTP sends credentials without encryption and is restricted to RFC1918 private IPv4 addresses. Use it only on a trusted management LAN. API-SSL/HTTPS verifies the router certificate through the OS trust store, or an independently obtained SHA-256 certificate fingerprint. For a self-signed certificate, export its public certificate through a trusted connection and run `openssl x509 -in router.crt -noout -fingerprint -sha256`. Assign a certificate to the encrypted router service; anonymous-DH API-SSL is unsupported.

3. Click Connect & inspect. The wizard reads the router and prepares operations for review.
4. For a captive portal, open Template editor, customize the page, choose the hotspot server and select Prepare direct installation. Confirm Upload & activate portal after reviewing shared-server effects. The app performs the folder copy and upload; WinBox file transfer is unnecessary.

The backend computer must be able to reach the router. Optional phone access to the owner interface still requires application HTTPS; this is independent of the router connection service.

The router password is not persisted in configuration, browser storage, or journals. It remains in process memory for the active connection. Disconnect and stop the process when finished. Other users or malware with access to the same OS account remain outside this pilot's security boundary.

## Supported scenarios

| Scenario | What is created | Prerequisites |
|---|---|---|
| Existing hotspot | A named local-user profile with upload/download limits and one simultaneous login | Enabled hotspot already configured and working |
| New paid hotspot | Gateway, DHCP pool/network/server, IPv4 input and forwarding rules, NAT, hotspot server/profile and voucher profile | Unused Ethernet port; working WAN; verified WAN firewall; global IPv6 disabled; FastTrack disabled; device-mode permits Hotspot; default hotspot files present |
| Office internet | Gateway, DHCP pool/network/server, IPv4 input and forwarding rules and NAT | Unused Ethernet port; working WAN; verified WAN firewall; global IPv6 disabled |

The new network is internet-only: forwarding toward RFC1918 and link-local destinations is blocked. Attach an external access point in AP/bridge mode to the spare port. Set wireless client isolation on that AP if clients must not communicate with each other; this application does not manage external APs or same-segment Layer 2 traffic.

**These are additive LAN scenarios, not factory-reset or full WAN installers.** The wizard never detaches a port from an existing bridge, changes a WAN, upgrades packages, changes global IPv6 settings, or resets the router. It refuses occupied ports and overlapping interface, DHCP-network and address-pool ranges. Existing firewall customizations can still conflict with the generated plan: review the exact operation list. A drop rule's presence is only a preliminary check, not a security audit.

Hotspot setup uses RouterOS default portal assets and `http-chap,cookie`, with local users and RADIUS disabled for the newly created profile. Branded one-field PIN and two-field portals can now be generated and activated through the [template editor workflow](TEMPLATES.md). The app copies and uploads portal files directly; HTTPS captive portal certificate provisioning is future work. For an existing hotspot, inspect its existing login methods and FastTrack exclusions yourself. Profile rate limits can be bypassed by unsuitable FastTrack configuration.

## Template editor and customer login pages

Customize branding, colors, ticket text, PIN/username-password layout, A4 columns and thermal widths with a sample preview. Save/import/export templates, generate either credential type, and print actual batches. Install a branded RouterOS portal directly with a recorded restore path, or download an optional overlay ZIP. See [TEMPLATES.md](TEMPLATES.md) for installation and compatibility details.

## Owner dashboard and mobile access

See connected users and sessions, first login for tracked tickets, expiry dates, and **expired but still connected** alerts. Search/filter accounts and disable, disconnect or re-enable valid tickets. The view refreshes every 15 seconds while visible and marks failed polls as stale. Older accounts without activation metadata show unknown first login.

The mobile web dashboard uses the same backend. See [MOBILE.md](MOBILE.md) for HTTPS LAN/VPN startup, certificate and token handling. See [API.md](API.md) for the future mobile-client contract.

## Planned Android and iOS applications

**Recommended stack: Dart with Flutter**, using one shared mobile codebase for Android and iPhone. Flutter is the framework; Dart is the language. This is the proposed mobile architecture, not an implemented or downloadable mobile application. The current release remains the Python backend with a responsive browser interface.

| Component | Technology | Responsibility |
|---|---|---|
| Android and iOS app | Flutter / Dart | Owner dashboard, setup screens, account actions, voucher preview and printing |
| Existing backend | Python | Router connections, validated setup operations, profile prices, voucher archives and change journals |
| Future standalone router client | Dart | Direct RouterOS API/API-SSL and HTTP/HTTPS communication from the phone |

### Stage 1: Mobile app connected to the existing backend

Build the Flutter interface against the application endpoints described in [API.md](API.md). Reuse the Python setup, expiry, pricing and voucher-history logic. The backend computer must remain running and reachable over the management LAN or VPN. Its saved prices and voucher history remain shared by owner devices using that backend. Review mobile authentication and session handling before release; the current launch-token model is intended for a single owner.

### Stage 2: Standalone phone-to-router operation

Implement the router connection layer, validation, change journaling, price storage and voucher archive in Dart so the phone can connect directly using the router IP, username, password and selected service. This stage removes the running-computer requirement for local management. It requires porting and testing the existing Python behavior; compiling the interface alone does not provide standalone operation. Define archive migration and synchronization before allowing owners to switch between independent phone and desktop stores.

The phone must have a network route to the MikroTik management address. A guest hotspot may require login or an explicitly permitted management path. Keep ticket expiry automation on the router so it does not depend on the mobile app staying open.

### Mobile implementation and release requirements

- Handle iOS local-network permission for connections to the router or backend.
- Implement platform-appropriate credential storage and certificate verification. Test any intentionally supported plain HTTP/API LAN mode against Android and iOS networking requirements.
- Validate voucher PDF generation, sharing and printing on actual supported printers. Desktop browser printing does not automatically provide native mobile printer support.
- Build and sign iOS releases using macOS and Xcode, locally or through a suitable macOS build service. App Store distribution requires Apple Developer Program enrollment.
- Test real Android and iPhone devices for LAN connections, network loss, interrupted writes, ticket actions, archive persistence and printing before publishing mobile releases.

References: [Flutter platform support](https://flutter.dev/development), [iOS build and release requirements](https://docs.flutter.dev/deployment/ios), and [Apple local-network privacy guidance](https://developer.apple.com/videos/play/wwdc2020/10110/).

## Vouchers and configurable expiry

1. Open Vouchers & users and review/install the router expiry checker with NTP synchronized.
2. Select an existing plain user profile and hotspot server.
3. Choose **elapsed**, **business-day closing**, **next-day startup**, **connected-time**, or **fixed date/time** expiry. Elapsed/connected modes support 1d, 3d, 7d and 28d. Daily policies have location and closing/fallback controls.
4. Choose PIN-only or independent username/password credentials and a print template. Confirm creation of 1–100 accounts. Each batch receives a dedicated profile with the first-login hook; existing custom hooks are not overwritten.
5. Print or export CSV. On the standard RouterOS page, PIN users enter the PIN in both fields. For single-field PIN login, install the generated portal as described in [TEMPLATES.md](TEMPLATES.md).
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
python3 -m unittest -v test_core test_http test_expiry test_mobile test_templates test_lan test_pricing test_voucher_history test_locations test_business test_gateways test_sales test_diagnostics
python3 -m py_compile core.py server.py expiry.py templates.py diagnostics.py llm_review.py
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

## Saved voucher reprinting

Use Vouchers & users → Saved vouchers to preview and print by batch or profile, 100 tickets per page. New batch credentials and prices persist in private local `data/vouchers` files; protect and back up this directory. Recover older router batches when passwords and Nelsonict batch markers are available. See TEMPLATES.md for recovery limits.

## Account table filters and sorting

In Hotspot accounts, search usernames, profiles or status; combine profile and Online/Offline/Disabled filters. Click User, Profile, Used, Allowance or Status headings to toggle ascending/descending order. Durations sort numerically and unlimited allowance sorts above finite limits. The displayed count reflects all active filters. Refresh retains filters and sorting; Reset filters & sort restores all accounts ordered by username.

The owner dashboard presents tickets in a compact table with a bounded scroll area, sticky column headings and action buttons pinned at the right edge. Search/status filters and automatic refresh remain available. Expired-but-connected tickets are highlighted.

## Payments and application backups

Create Paystack, Monnify or Flutterwave checkout links using saved NGN profile prices. The running backend verifies successful payments and automatically issues one voucher per order for the connected location. Retrieve issued tickets from Saved vouchers; SMS/email delivery and a public captive-portal shop are not included. Select a provider and configure its backend credentials as documented in PAYMENTS.md; start in test/sandbox mode. See [PAYMENTS.md](PAYMENTS.md) for setup, payment state, interruption handling and live-testing requirements.

Download and restore profile prices, templates, voucher archives and saved location settings from Connection guide. Restores preview replacements and save a recovery copy first. Backup files contain voucher passwords; payment orders and secrets are excluded. See [BACKUPS.md](BACKUPS.md).


## SQLite sales ledger and daily/monthly reports

Open **Sales reports** after connecting to a location. Filter the date range and profile, select Daily or Monthly, and set the UTC offset (Nigeria: +60 minutes). Totals group by profile and currency; Export report CSV downloads the displayed totals. Values are gross recorded sales, before gateway fees/refunds, not profit or provider settlement balances.

The inventory lists confirmed archived vouchers as sold, unsold, payment pending/review or test. Filter by profile, batch, username and status. Record cash sales at the actual amount received, or correct a mistaken cash entry back to unsold with an audit record. Unsold means no recorded sale; old cash sales are not guessed from ticket use. Expiry and account access remain separate from sale status.

Verified, issued live-provider orders are indexed automatically when sales reports load. Test payments and paid-but-unissued/review orders do not count as sales. Each voucher has at most one active sale. New online sales use issuance time; older orders without that timestamp fall back to verification/order-creation time and may need historical reconciliation.

Python's built-in SQLite stores inventory metadata and sale/correction records in `data/sales.sqlite3`, with schema versioning, indexes and transactional writes. Money uses integer minor units. This database contains no voucher or router passwords. Existing templates, credentials, payment orders and router settings retain their established stores; no wholesale migration is required. SQLite data is included in the application backup/restore tool. See [SALES.md](SALES.md).
