# Nelsonict Router Manager

A local MikroTik management application for **Nelsonict Services Limited**: connect a router, inspect its configuration, review a setup plan, apply additions, and create printable hotspot vouchers.

**Version 0.4.0 — pilot, not a production-certified release.** Targets RouterOS v7 API and REST services. RouterOS **7.24.2 is the requested compatibility target and has not been verified on hardware**. The official changelog page available during development did not establish that exact release. No real router was connected during development.


## Start here

For a first deployment, use an **existing working hotspot** and test one local voucher before selling batches. The application runs on the owner's computer; RouterOS enforces installed ticket expiry. Internet access is needed for optional AI/payment services, while local management requires a reachable router management address.

| Your goal | Start with |
|---|---|
| Try the interface without a router | [Run from source](#run-from-source), then Open demonstration |
| Connect an existing hotspot and sell tickets | [First-sale walkthrough](#first-sale-walkthrough) |
| Create a new hotspot or isolated office LAN | [Supported scenarios](#supported-scenarios) |
| Choose rules for stable or intermittent electricity | [Choosing an expiry policy](#choosing-an-expiry-policy) |
| Print branded tickets or install a PIN portal | [Templates](#template-editor-and-customer-login-pages) |
| Collect online payments | [Payment configuration](#payment-configuration) |
| Manage a remote location or RADIUS users | [Remote control and User Manager](#remote-control-and-user-manager) |
| Access the dashboard from a phone | [Phone connection example](#phone-connection-example) |
| Upgrade an existing installation | [Upgrade and migration](#upgrade-and-migration) |
| Resolve an error or interrupted operation | [Troubleshooting](#troubleshooting) |
| Find implementation and release information | [Development](#development-and-verification) and [documentation index](#documentation) |

## First-sale walkthrough

1. **Prepare the site.** Verify that the existing hotspot already provides internet, preserve a separate router backup, and keep independent management access. Install/run the application and select the enabled management service.
2. **Save the location and connect.** Enter its name, IPv4 address, username and service settings. Supply the session password and inspect the router. Reuse this saved location so subsequent archives and orders stay associated with it.
3. **Prepare a profile.** Use the existing-hotspot scenario if you need a new local-user profile. Review its rate limits and operation list, acknowledge your backup and apply the reviewed plan. Use a plain profile without custom login/logout scripts for tracked vouchers.
4. **Verify time and expiry.** Synchronize router NTP, then open **Vouchers & users → Review / install engine**. Review and install the app-owned automation. Choose the policy using the examples below.
5. **Set the price and ticket design.** Save a profile price/currency. In **Template editor**, choose PIN or separate credentials, branding, and paper layout. For one-field PIN login, prepare and install the corresponding portal on the intended hotspot server.
6. **Test one voucher.** Generate one ticket, preview it and log in from a customer device. Check first activation, rate limiting, disconnect/disable behavior and the selected expiry policy. Confirm that printing fits the intended printer.
7. **Generate sale stock.** Create the desired batch, up to 100 tickets. Use Saved vouchers to reprint by batch or profile. For a cash sale, record the amount in Sales reports; generating or printing alone does not record a sale.
8. **Add payments if required.** Configure a provider in sandbox/test mode, restart the backend, reconnect the location and test a checkout through verified issuance. Deliver the resulting voucher to the customer yourself.
9. **Close the business day.** Review connected/expired tickets, pending payment orders and sales totals. Save an application backup and periodically make a stopped full-data-folder backup. Keep the backend running whenever payment verification is expected to continue.

## Review fixes — 13 September 2026

- Startup expiry now shortens a previously stored next-day fallback when an earlier next-day boot requires expiry at boot +10 minutes. It never extends the stored deadline or re-enables expired accounts.
- **Existing installations:** update the application, connect with NTP synchronized, then use **Vouchers & users → Review / install engine**. Review the listed scheduler/profile changes and install them. Exact known previous Nelsonict scheduler and login-hook sources are upgraded; custom scripts are not overwritten. Updating desktop files alone does not update router scripts.
- Rollback marks affected archived vouchers revoked before attempting router deletion. Revoked stock is excluded from saved reprints and sellable inventory; recorded sales remain in reports. Older successful rollback journals are reconciled when their location archive loads. Keep those journals when migrating old installations. Failed rollback leaves affected stock quarantined until manually reconciled.
- The Print button revalidates archived tickets, and rollback clears the current browser preview. Previously downloaded files or printed tickets cannot be recalled. Deletions made independently in WinBox still require reconciliation; this fix covers application rollback and retained rollback journals.
- Diagnostic schema version 1 retains validated expiry metadata and script/hook presence flags on JSON roundtrip. Legacy projections remain readable. RSC import keeps only parsed managed-policy metadata and presence flags, without retaining secrets or script bodies.
- AI and provider calls run outside the router-operation lock. Payment processing has a separate serialization lock; issuance rechecks the captured router connection under the state lock. Switching away leaves unissued orders pending at their original location. Checkout initialization results remain saved there. Stale AI results are rejected, and browser controls remain usable while cloud calls wait.

All 170 Python tests, JavaScript syntax checks and a frontend concurrency regression passed locally. Real RouterOS script execution, physical reboot behavior and live provider acceptance still require hardware testing.

## Features at a glance

| Area | Available now |
|---|---|
| Router connections | API/API-SSL and HTTP/HTTPS REST over LAN/VPN; multiple saved locations, one active router |
| Setup | Reviewed additive plans for existing hotspots, new paid hotspots and office internet |
| Vouchers | PIN-only or username/password tickets, five expiry policies, profile prices and saved batch/profile printing |
| Owner dashboard | Connected sessions, tracked first login, expiry status, compact tables, filters and account actions |
| Templates | Printable voucher customization and direct captive-portal installation |
| AI walkthrough | Setup snapshots, imported export review, optional AI suggestions and reviewed bulk repairs |
| Payments | Paystack, Monnify and Flutterwave checkout with backend verification and voucher issuance |
| Sales | SQLite inventory, sold/unsold tracking and daily/monthly totals by profile |
| Backups | Preview and restore application metadata, voucher archives and sales records |
| Distribution | Windows EXE and Debian DEB build scripts; manual GitHub package workflow |

## Run from source

Requires **Python 3.11 or newer** and a current desktop browser. No pip or npm packages are required to run from source. The Windows EXE bundles Python; building it requires PyInstaller. The DEB uses system Python.

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

Open **Desktop packages** in the app for build options, or use the commands below from the downloaded source folder.

| Target | Build command | Output | Runtime requirement |
|---|---|---|---|
| Windows | `build-windows.bat` on Windows | `dist/NelsonictRouterManager.exe` | Browser; Python is bundled |
| Debian / Ubuntu | `sh build-deb.sh` with Python 3.11+ and dpkg-dev | `dist/nelsonict-router-manager_0.4.0_all.deb` | Browser and system Python 3.11+ |

Install and launch the Debian package:

```sh
sudo apt install ./dist/nelsonict-router-manager_0.4.0_all.deb
nelsonict-router-manager
```

Alternatively, open [Build desktop packages](https://github.com/edunelsonit/nelsonict-router-manager/actions/workflows/packages.yml), select **Run workflow**, and download the Windows or Debian artifact after its job succeeds. Extract the downloaded artifact ZIP. Workflow permission is required; these are generated artifacts, not prepublished release downloads.

The EXE is an unsigned portable application, not a Windows installation wizard. Both packages use the same browser interface and require the backend to remain running. The DEB includes an applications-menu launcher. See [PACKAGING.md](PACKAGING.md) for build dependencies and migration.

### Where owner data is stored

| Installation | Default data directory |
|---|---|
| Source checkout | `data/` beside `server.py` |
| Windows EXE | `%LOCALAPPDATA%/nelsonict-router-manager` |
| DEB | `~/.local/share/nelsonict-router-manager`, or `$XDG_DATA_HOME/nelsonict-router-manager` |

Set `NELSONICT_DATA_DIR` to override the location. References to `data/` below mean this active data directory. Packaged data stays outside the application files and EXE extraction folder. Before migrating, stop the backend and copy its complete data folder to the new location; do not run two backends against the same folder. A stopped full-folder backup retains payment orders that application JSON backups exclude.

## Why this stack

- **Python backend:** cross-platform networking, certificate verification, input validation and operation journaling, with no installation dependency chain.
- **HTML, CSS and JavaScript:** a responsive browser interface without a build step or external CDNs.
- **RouterOS API/API-SSL and HTTP/HTTPS REST:** structured commands with explicit transport selection.
- **Local execution:** your router's private IP is reachable from your LAN or management VPN. A publicly hosted web page or GitHub Pages cannot replace this backend.

This is a desktop-hosted, single-owner application with a mobile web interface. Owners can access it through optional HTTPS on a trusted LAN or VPN. It is not a native Android/iOS app or multi-tenant SaaS. All authorized owner devices share one active router connection.

## Remote control and User Manager

Use **Remote control** to select a reachable remote router and encrypted API-SSL/HTTPS service, then connect and save the location. A management VPN or configured inbound path is required. The app does not automatically create a tunnel.

Use **User Manager** for RouterOS v7 RADIUS service settings, router clients, profiles, limitations, user/group management and profile assignments. Review every change, configure the hotspot RADIUS client and accounting, and inspect session records. The matching user-manager package must already be installed. These accounts remain separate from local-hotspot vouchers and payment issuance. See [USER_MANAGER.md](USER_MANAGER.md) for the full setup sequence and unsupported operations.

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

## Choosing an expiry policy

Electricity availability does not select a policy automatically. Choose the rule that matches what the customer is buying; a stable-power location can still sell either elapsed or connected-time packages.

| Policy | Suitable offer | Example and power behavior |
|---|---|---|
| Elapsed | A fixed period from first use | A 1-day ticket activated Monday at 09:00 expires Tuesday at 09:00, including offline time and power cuts. |
| Connected-time | A purchased allowance of actual use | A 1-day allowance means 24 accumulated online hours; disconnected time does not consume the allowance. |
| Business-day closing | Access until the next closing time | With closing at 22:00, a ticket activated at 14:00 ends at 22:00. Activation exactly at closing uses the following day's closing. |
| Next-day startup | A daily offer tied to the next day's restart | A used ticket from Monday expires at 08:10 after a Tuesday 08:00 boot. If the router stays on overnight, the configured fallback applies instead. |
| Fixed date/time | An event or shared absolute deadline | All tickets in the batch expire at the selected instant, even if never used. |

For startup tickets, an earlier next-day boot shortens a future stored fallback: a stored 10:10 fallback becomes 08:10 after an 08:00 boot. Later restarts never extend a deadline, and expired accounts are never revived. Unused startup tickets do not expire simply because midnight passes. Existing installations need the engine upgrade described below.

Elapsed/connected durations are 1 day, 3 days, 7 days or 28 days. Business/startup policies use daily scheduling settings instead. Policy offsets are fixed minutes from UTC (Nigeria: +60); they do not automatically change for daylight saving. First activation and enforcement depend on the clock rules in [EXPIRY.md](EXPIRY.md), and scheduler checks run at 30-second intervals.

## Profile prices

Save a price and currency for each hotspot user profile in **Vouchers & users**. Newly generated voucher archives retain their price snapshot for printing and sales tracking. Updating a profile price does not rewrite previously archived ticket prices. Payment checkout uses saved NGN profile prices; printing a price does not itself mark a voucher sold.

## Vouchers and configurable expiry

1. Open Vouchers & users and review/install the router expiry checker with NTP synchronized.
2. Select an existing plain user profile and hotspot server.
3. Choose **elapsed**, **business-day closing**, **next-day startup**, **connected-time**, or **fixed date/time** expiry. Elapsed/connected modes support 1d, 3d, 7d and 28d. Daily policies have location and closing/fallback controls.
4. Choose PIN-only or independent username/password credentials and a print template. Confirm creation of 1–100 accounts. Each batch receives a dedicated profile with the first-login hook; existing custom hooks are not overwritten.
5. Print or export CSV. On the standard RouterOS page, PIN users enter the PIN in both fields. For single-field PIN login, install the generated portal as described in [TEMPLATES.md](TEMPLATES.md).
6. Inspect the owner dashboard. Expiry disables accounts and removes active sessions/cookies while keeping account records. Owner controls work on any local hotspot account, including older tickets.

The scheduler and activation record live on the router so enforcement does not depend on the management app staying open. **Native scripts still require real-router acceptance testing.** The checker runs every 30 seconds; this is not a second-exact cutoff guarantee. Location scheduling uses an explicit fixed UTC offset (Nigeria +60 minutes), without automatic daylight-saving changes. See [EXPIRY.md](EXPIRY.md) for exact policies and clock/power-loss behavior.

### If expiry installation asks for NTP synchronization

The installer requires verified router time. Enable the router's NTP client, configure reachable time servers, and wait for its status to show **synchronized** before retrying. A manually entered clock alone does not satisfy the check. For Nigeria, use the appropriate local timezone and +60-minute policy offset.

If the message persists, inspect these read-only terminal results:

```routeros
/system ntp client print
/system ntp client servers print detail
/system clock print
```

Check router Internet/DNS access and whether the application account can read those menus. See [EXPIRY.md](EXPIRY.md) for clock handling. The current AI walkthrough does not automatically configure NTP.

Legacy API callers that omit `expiry_mode` retain connected-time-only behavior. Historical first-login timestamps cannot be recovered for older accounts. No automatic migration guesses those dates. Do not manually edit managed `ns2,` comments.

## Saved voucher reprinting

Use Vouchers & users → Saved vouchers to preview and print by batch or profile, 100 tickets per page. New batch credentials and prices persist in private local `data/vouchers` files; protect and back up this directory. Recover older router batches when passwords and Nelsonict batch markers are available. See TEMPLATES.md for recovery limits.

## Account table filters and sorting

In Hotspot accounts, search usernames, profiles or status; combine profile and Online/Offline/Disabled filters. Click User, Profile, Used, Allowance or Status headings to toggle ascending/descending order. Durations sort numerically and unlimited allowance sorts above finite limits. The displayed count reflects all active filters. Refresh retains filters and sorting; Reset filters & sort restores all accounts ordered by username.

The owner dashboard presents tickets in a compact table with a bounded scroll area, sticky column headings and action buttons pinned at the right edge. Search/status filters and automatic refresh remain available. Expired-but-connected tickets are highlighted.

## Payments and application backups

Create Paystack, Monnify or Flutterwave checkout links using saved NGN profile prices. The running backend verifies successful payments and automatically issues one voucher per order for the connected location. Retrieve issued tickets from Saved vouchers; SMS/email delivery and a public captive-portal shop are not included. Select a provider and configure its backend credentials as documented in PAYMENTS.md; start in test/sandbox mode. See [PAYMENTS.md](PAYMENTS.md) for setup, payment state, interruption handling and live-testing requirements.

Download and restore profile prices, templates, voucher archives, SQLite sales records and saved location settings from Connection guide. Restores preview replacements and save a recovery copy first. Backup files contain voucher passwords; payment orders and secrets are excluded. See [BACKUPS.md](BACKUPS.md).


## Payment configuration

Set credentials in the **backend process environment**, then restart the app. No `.env` loader or browser credential form is provided. Configure only the providers you intend to use; never place secrets in source files, ticket templates or GitHub.

| Integration | Environment variables | Notes |
|---|---|---|
| Paystack | `PAYSTACK_SECRET_KEY` | Test/live mode follows the key prefix. |
| Monnify | `MONNIFY_API_KEY`, `MONNIFY_SECRET_KEY`, `MONNIFY_CONTRACT_CODE`, `MONNIFY_REDIRECT_URL` | `MONNIFY_MODE` defaults to `test`; explicitly set `live` for live processing. Customer name is required. |
| Flutterwave | `FLUTTERWAVE_SECRET_KEY`, `FLUTTERWAVE_REDIRECT_URL` | Uses the v3 Standard checkout integration; test/live mode follows the key. |
| Optional AI review | `OPENAI_API_KEY`, `OPENAI_MODEL` | Both are required for cloud analysis; local diagnostic checks remain available without them. |
| Data directory | `NELSONICT_DATA_DIR` | Optional path override for all owner data; set it before starting the backend. |

Redirect URLs must be HTTPS receipt/instruction pages you control. The app does not deploy those pages. A redirect does not authorize a voucher: the backend verifies payment reference, amount, currency, customer and provider mode before issuance. Customers receive the hosted checkout link, never the private owner launch URL. Checkout requires customer internet access; walled-garden provisioning is not included.

**Operational sequence:** save a positive NGN profile price → select the ticket settings → create a checkout link → customer pays → backend verifies → one voucher is issued → owner retrieves and delivers it. Each order snapshots its price/settings. The background worker checks up to three pending orders per pass, normally every 30 seconds; provider latency can extend that interval.

| Order condition | Owner response |
|---|---|
| Pending | Keep the original location connected; use Check payments or wait for the worker. |
| Initialization interrupted | Inspect the provider dashboard and stored order before creating a replacement checkout. |
| Issued | Retrieve the existing voucher; do not create another ticket for the same payment. |
| Issuing after a crash, needs-review, or verification-mismatch | Compare provider records, voucher archive and change journal. Resolve the actual router write and payment before manually delivering a replacement or refund. |
| Location disconnected or switched | Reconnect the original saved location to resume eligible pending orders. |

Automatic issuance is attempted at most once after intent is persisted. An uncertain router write is not automatically retried. Changing provider keys/mode can prevent new credentials from processing old orders. Refunds, disputes, automatic revocation and a payment-recovery console are not implemented. See [PAYMENTS.md](PAYMENTS.md) before enabling live payments.

## SQLite sales ledger and daily/monthly reports

Open **Sales reports** after connecting to a location. Filter the date range and profile, select Daily or Monthly, and set the UTC offset (Nigeria: +60 minutes). Totals group by profile and currency; Export report CSV downloads the displayed totals. Values are gross recorded sales, before gateway fees/refunds, not profit or provider settlement balances.

The inventory lists confirmed archived vouchers as sold, unsold, payment pending/review or test. Filter by profile, batch, username and status. Record cash sales at the actual amount received, or correct a mistaken cash entry back to unsold with an audit record. Unsold means no recorded sale; old cash sales are not guessed from ticket use. Expiry and account access remain separate from sale status.

Verified, issued live-provider orders are indexed automatically when sales reports load. Test payments and paid-but-unissued/review orders do not count as sales. Each voucher has at most one active sale. New online sales use issuance time; older orders without that timestamp fall back to verification/order-creation time and may need historical reconciliation.

Python's built-in SQLite stores inventory metadata and sale/correction records in `data/sales.sqlite3`, with schema versioning, indexes and transactional writes. Money uses integer minor units. This database contains no voucher or router passwords. Existing templates, credentials, payment orders and router settings retain their established stores; no wholesale migration is required. SQLite data is included in the application backup/restore tool. See [SALES.md](SALES.md).

## Phone connection example

The phone connects to the running Python backend, which connects to the router. These are two separate connections with separate certificates and network requirements. For an owner computer at `192.168.10.20`, use a certificate trusted by the phone whose subject alternative name includes that IP:

```sh
python3 server.py --listen 192.168.10.20 --port 8765 --tls-cert /private/server.crt --tls-key /private/server.key --no-browser
```

Replace the address and certificate paths with your own. On Windows, use `py -3 server.py` with the same flags and Windows paths. Open the exact launch URL printed by the process on the phone. Restrict the computer firewall to owner devices or the management VPN. Non-loopback HTTP, `0.0.0.0` and public backend bind addresses are refused.

Restarting the app changes the launch token, so reopen the new link on every owner device. All devices share full owner access and one active router; there are no staff roles or individually revocable device accounts. Away from the site, connect through an existing management VPN. Remote control does not create tunnels, configure port forwarding or bypass Starlink/carrier NAT. Router address input currently accepts IPv4 literals, not DDNS hostnames or IPv6.

## Upgrade and migration

1. Record the current application version and active data path. Resolve or record outstanding payment and uncertain-write cases before maintenance.
2. Stop the backend. Copy its **entire data directory** to a private backup location, including payment orders and change journals. Preserve router configuration and User Manager database backups separately.
3. Install the updated source or package. Keep the prior application and data backup available for recovery. For source updates, preserve the existing `data/` folder; when changing installation type, move the complete data folder to its new default path or point `NELSONICT_DATA_DIR` to it.
4. Start one backend instance. Use its new launch URL and verify saved locations, prices, templates, archives and reports. Do not run old and new versions against the same folder or allow two copied installations to process the same payment orders.
5. Reconnect the intended saved location and synchronize router NTP. Open **Vouchers & users → Review / install engine**, review the affected scheduler/profile sources and install the upgrade. Exact known older Nelsonict sources can be upgraded; modified/custom sources require manual review. Updating application files alone leaves old router automation installed.
6. Test one voucher and inspect existing tracked tickets. Keep historical rollback journals: archive loading uses them to quarantine previously rolled-back stock. Independently deleted router users still need manual reconciliation.
7. If recovery is needed, stop the backend first. Preserve the failed installation's data for investigation. Restore a compatible application/data pair only after reconciling any payments and router changes since the backup; restoring old local files does not undo router writes or provider payments.

### What each backup protects

| Data | Application JSON backup | Stopped full data-folder copy |
|---|---|---|
| Saved location settings and IDs | Included; no router passwords | Included; no session passwords |
| Profile prices, templates and voucher archives | Included, including readable voucher credentials | Included |
| SQLite inventory and sales corrections | Included as validated ledger rows | Included as local database files |
| Payment orders and issuance state | Excluded | Included |
| Change journals and other local recovery state | Not a full journal backup | Included |
| Backend environment secrets and external TLS keys | Excluded | Preserve separately if outside the data directory |
| Router configuration and User Manager database | Excluded | Excluded; take separate router-side backups |

Application restore requires a disconnected router, preview and the word `RESTORE`. It saves a recovery copy first, replaces matching files and retains files absent from the backup. It does not recreate router users or redeploy portals. Treat backups and voucher CSVs as credentials: backups are not encrypted by the application. See [BACKUPS.md](BACKUPS.md) for import limits and partial-restore recovery.

## Plan, apply and recovery

- Plan generation reads router configuration and performs scenario-specific checks.
- The plan lasts 10 minutes and binds to a configuration fingerprint. A changed configuration requires a new plan. No live lock exists on RouterOS; avoid concurrent WinBox edits while applying.
- Apply requires backup acknowledgment and the literal word `APPLY`.
- Every operation is journaled before sending. Successful create responses record the returned RouterOS object ID.
- A lost/error response is marked **uncertain** and stops subsequent writes. The app never automatically retries a write.
- Open Change history to inspect results. Rollback removes known additions in reverse order and stops if an object differs from the recorded creation values.
- Rollback is **not a transaction or RouterOS Safe Mode**. It cannot reverse uncertain writes, all side effects, arbitrary later modifications or a lost management connection. Inspect uncertain writes manually using their recorded menu and properties. On router reset/replacement, do not reuse old change records.
- Setup rollback can disconnect users. Rolling back a voucher batch deletes those users. Do not rollback a populated hotspot profile until dependent vouchers have been dealt with.

Local journals live in `data/`, with restrictive POSIX modes where supported. They contain router addresses and voucher identifiers (which are also PINs), so treat them as secrets. Windows users should keep the project in a private user folder with appropriate ACLs. `data/`, exports, backups, private keys and launch/runtime state are excluded from Git. The app serves an explicit allowlist of frontend assets; journals are never exposed as static files.

## Troubleshooting

| Symptom | Check and next action |
|---|---|
| Browser does not open / port is occupied | Open the printed launch URL manually. Try `--port 8766`; keep the backend terminal open. |
| Unauthorized page after restarting | Use the new launch URL. Its previous per-process token is no longer valid. |
| Router connection times out | Verify the IPv4 address, selected API/REST service and custom port, local/VPN route, router firewall and whether guest-hotspot access permits management. |
| Login or permission denied | Check router credentials and service policies (`api` or `rest-api`) plus read/write access. Script/UM operations can require additional permitted menus. |
| TLS verification fails | Check the service certificate and trust chain, or independently verify its SHA-256 fingerprint. Phone-to-backend trust is separate from backend-to-router trust. |
| Wizard refuses an interface or network | Use a genuinely unused Ethernet port and non-overlapping subnet/pool. The wizard does not detach bridge members or repair the WAN. Review the specific prerequisite error. |
| NTP synchronization required | Inspect router NTP client/server status, time and reachability. Wait for synchronized status; a manually set clock is insufficient. |
| Engine source differs | Preserve and inspect the existing script. Only exact recognized Nelsonict automation can be upgraded automatically; custom sources are not overwritten. |
| First login is unknown | Older tickets lack an activation record. Do not infer historical activation from a current session start. |
| Expired ticket is still connected | Check the last refresh, NTP, managed metadata, hook/scheduler and router log. Disable the local account explicitly if required; investigate automation before more sales. |
| Deleted/rolled-back voucher is missing from prints | Application rollback intentionally revokes that stock. Inspect its change journal and router state; a failed deletion still leaves the archive quarantined. |
| Online payment has no ticket | Reconnect the original location, inspect the order state and provider response, then compare archive/journal/router records. Do not blindly retry an uncertain issuance. |
| Sales totals differ from bank settlement | Reports contain recorded gross sales, exclude test/unissued orders, and do not subtract provider fees/refunds. Check profile/date/UTC-offset filters and unrecorded cash sales. |
| Portal fails to authenticate PIN users | Match the template to the credential mode and actual hotspot server/profile. Preserve RouterOS support files, including CHAP assets; use the documented portal restore path if necessary. |
| User Manager menu is unavailable | Verify the matching installed package and account permissions. Package installation/reboot is outside the application. |
| AI result is rejected after switching routers | Take a fresh snapshot on the current connection. Stale cloud results cannot authorize changes to another location. |
| Dashboard shows stale data | Restore backend/router connectivity and refresh. The view is a sampled snapshot, normally refreshed every 15 seconds. |

When reporting a problem, include application version, installation type, exact RouterOS version/architecture, selected transport, scenario, error text and whether the write is uncertain. Share a reviewed diagnostic projection when useful. Remove launch tokens, passwords, payment keys, private keys and customer voucher credentials. Network names/addresses can remain in diagnostic evidence; inspect it before sharing.

## Current operating limits

- **Attended pilot:** real-router execution, power-cycle behavior and live payment acceptance remain release gates. Automated tests do not certify RouterOS 7.24.2 compatibility.
- **Prepared networks:** no factory-reset installer, WAN provisioning, Wi-Fi/AP controller, VLAN/bridge designer, multi-WAN or PPPoE deployment. The office scenario blocks private routed destinations and is not a shared camera-network design.
- **One owner backend:** one active location, shared owner token and one process per data store. AI/provider waits release the main operation lock; router operations still serialize and can take time.
- **Separate RADIUS workflow:** User Manager settings, users, profiles and limitations are supported, but local voucher printing, payment issuance, SQLite sales and Nelsonict startup expiry do not automatically apply to RADIUS accounts. Disabling a User Manager user does not guarantee immediate remote NAS disconnection.
- **Bounded automation:** AI selects supported repair types; it cannot execute arbitrary suggested commands, infer lost activation dates or repair every configuration. Diagnostic imports are evidence, not executable router backups.
- **Scale not benchmarked:** retained accounts, per-batch profiles, 30-second expiry scans and 15-second dashboard polling need capacity testing on the intended router. No certified maximum client count is claimed.
- **Native mobile remains planned:** the responsive browser interface is available now; a Flutter Android/iOS application and standalone phone-to-router operation still require implementation.

See [PROJECT_REVIEW.md](PROJECT_REVIEW.md) for the audit and fix addendum, including remaining setup-fingerprint and prerequisite coverage gaps. Avoid concurrent configuration edits; a reviewed plan is not a complete guarantee that every external dependency is unchanged.

## Project layout

| Files | Responsibility |
|---|---|
| `server.py`, `web/` | Local HTTP/HTTPS backend, owner endpoints and browser interface |
| `core.py`, `api_transport.py` | Router inspection, scenario planning, validated operations and transports |
| `expiry.py`, `voucher_history.py`, `pricing.py` | Ticket policy/automation, archived credentials and profile price snapshots |
| `templates.py`, `portal_install.py` | Voucher/portal rendering and reviewed portal installation |
| `diagnostics.py`, `llm_review.py` | Projected evidence, supported repairs and optional AI review |
| `gateways.py`, `payments.py`, `sales.py` | Provider adapters, order/issuance state and SQLite sales ledger |
| `locations.py`, `backups.py`, `app_paths.py` | Saved locations, backup/restore and installation-specific storage |
| `user_manager.py` | Allowlisted RouterOS User Manager/RADIUS configuration |
| `packaging/`, build scripts, `.github/workflows/` | Desktop package creation and automated checks |
| `test_*.py`, `test_cloud_ui.js` | Simulated-router, storage, transport and concurrency regression checks |

## Development and verification

```sh
python3 -m unittest discover -v
python3 -m py_compile core.py server.py expiry.py templates.py diagnostics.py llm_review.py app_paths.py packaging/build.py
node --check web/app.js
node --check web/diagnostics.js
node --check web/business.js
node --check web/sales.js
node --check web/templates.js
node --check web/table-utils.js
node --check web/user-manager.js
node test_cloud_ui.js
```

Node is optional for running the application and is used for JavaScript syntax and frontend concurrency checks during development. GitHub Actions includes Python checks on Ubuntu and Windows. A successful simulation test does not establish MikroTik compatibility.

**Last recorded local checks:** 170 Python tests passed, frontend syntax and navigation checks passed, and the DEB built, extracted and passed an entrypoint smoke check. Windows EXE build/launch, installed desktop launch, browser visual checks, real-router expiry and live AI/payment acceptance remain unverified. These are recorded local results, not a claim that GitHub CI or hardware certification passed. See [VALIDATION.md](VALIDATION.md).

See [ACCEPTANCE.md](ACCEPTANCE.md) for real-router release gates and [ROADMAP.md](ROADMAP.md) for the broader product plan.

## Reference archive

The supplied `Mikhmon Server.zip` was inspected as a feature reference. Its `include/version.php` reports **3.20 06-30-2021**; it contains 98 PHP files, a RouterOS PHP API class, hotspot/user/profile management and voucher printing. The archive contains a GPL v2 license text. This project contains newly authored code and does not redistribute the supplied PHP code, server binaries, assets or configuration data. This repository uses the GPL-3.0 license selected when the repository was created; see [LICENSE](LICENSE).

## RouterOS references

- [REST API: HTTPS services, authentication and CRUD methods](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API)
- [Hotspot: IPv4, device-mode, profiles and user limits](https://help.mikrotik.com/docs/spaces/ROS/pages/56459266/HotSpot+-+Captive+portal)
- [Configuration backup/export and Safe Mode](https://help.mikrotik.com/docs/spaces/ROS/pages/328155/Configuration+Management)
- [Official downloads and changelogs](https://mikrotik.com/download/changelogs)

The linked legacy documentation warns that it is frozen; MikroTik directs readers to its [current manual](https://manual.mikrotik.com/docs/introduction/). Confirm behavior on the exact deployed version before business use.


## Documentation

| Guide | Details |
|---|---|
| [Remote control / User Manager](USER_MANAGER.md) | Remote prerequisites, RADIUS setup, supported fields and recovery |
| [Project review](PROJECT_REVIEW.md) | Practicality audit, addressed defects and remaining gaps |
| [Packaging](PACKAGING.md) | EXE/DEB builds, artifacts and data migration |
| [Expiry](EXPIRY.md) | Ticket policies, activation records and clock behavior |
| [Templates](TEMPLATES.md) | Ticket printing, saved batches and portal installation |
| [AI walkthrough](DIAGNOSTICS.md) | Evidence sharing, supported repairs and comments |
| [Payments](PAYMENTS.md) | Provider credentials and payment verification |
| [Sales](SALES.md) | Inventory, cash entries and SQLite reports |
| [Backups](BACKUPS.md) | Backup scope and recovery |
| [Mobile access](MOBILE.md) | HTTPS browser access from phones |
| [API](API.md) | Owner application endpoints |
| [Validation](VALIDATION.md) / [Acceptance](ACCEPTANCE.md) | Completed checks and outstanding release gates |
| [Roadmap](ROADMAP.md) | Planned work |
