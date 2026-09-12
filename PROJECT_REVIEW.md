# Project and setup practicality review

**Review date:** 12 September 2026  
**Reviewed GitHub revision:** d39fc362b8cdd861dfe42e542211c771562e8104  
**Decision:** suitable for continued lab evaluation and an attended pilot after the high-priority defects below are fixed. Not ready to promise unattended commercial hotspot operation, complete User Manager management, or a turnkey ISP installer.

The Python/backend and browser architecture is appropriate for a small, local, single-owner management application. The major remaining problem is consistency between ticket lifecycle, actual router state and business records, together with insufficient hardware evidence. A language rewrite would not resolve these issues.

## Evidence and limits

Reviewed the setup planner, router transports, expiry implementation, diagnostic/AI path, User Manager controls, payment adapters and issuance, sales/archives, backup/restore, portal/template workflow, browser integration, packaging and release documentation. Reran all **156 Python tests**, successfully, plus syntax checks for all browser JavaScript files. Used the demonstration router and direct evaluator calls to reproduce the findings identified below. These were isolated checks; no live router, customer account or payment was changed.

This is a source and simulated-behavior review, not a penetration test, browser visual audit, firmware certification or bandwidth benchmark. Existing tests largely exercise Python behavior and mocked transport. They do not execute the bundled expiry scripts inside RouterOS. Windows execution, live provider settlement, physical reboot behavior, RADIUS sessions and real portal login remain unverified.

## Priority findings

### F1 — High: fallback expiry can override the intended next-day boot deadline

**Evidence:** expiry.py, deadline(), and the native script block that calculates due only while due=0.

Reproduced this timeline using Nigeria time:

1. A startup-policy ticket first logs in on September 10 at 12:00.
2. Router remains on at September 11, 00:01. The scheduler logic assigns the configured fallback: September 11, 10:10.
3. The router subsequently powers off and boots at 08:00.
4. Because the fallback is already stored as a nonzero due value, the evaluator retains 10:10 instead of using 08:10.

The reproduced result is two hours later than the intended boot-plus-ten-minutes rule. The native script contains the same persistence condition; actual firmware execution still needs testing. This matters when electricity schedules change or a site is on past midnight.

**Required change:** distinguish a provisional no-reboot fallback from a committed boot-derived deadline. Define how a subsequent boot affects the provisional deadline, preserve expired/disabled status, and test midnight crossing, delayed NTP, repeated reboots, missed operating days and no-reboot sites in both the Python evaluator and RouterOS script.

### F2 — High: rolled-back vouchers remain printable and available for sale

**Evidence:** server.py rollback route, voucher_history.confirmed(), sales.SalesDB.sync().

Reproduced through application routes: create one voucher, roll back its journal, then request its saved batch and sales report. Router accounts=0; reprintable vouchers=1; sales inventory shows that voucher as available/unsold. Rollback removes the router account but never updates its archived creation_state. Sales availability is derived from that archive.

An attendant can hand out or record a sale for a ticket the application itself deleted. Retaining historical credentials is useful; presenting deleted stock as sellable is not.

**Required change:** separate creation history from current lifecycle status. Record revoked/rolled-back/missing states, exclude them from sellable inventory, label historical reprints, and retain past sales for accounting instead of erasing them. Also reconcile deletions performed outside the application.

### F3 — Medium: downloaded diagnostic evidence loses information when reimported

**Evidence:** diagnostics.project() and import_file().

Reproduced a valid managed policy converted to the application JSON projection, then reimported that JSON. The original expiry_metadata object became null. The projection recalculates metadata from comment, but the exported projection deliberately contains no raw comment. Script/hook presence flags have the same reconstruction problem. The RSC parser also drops comments before attempting policy interpretation.

**Required change:** version the diagnostic export schema and validate already-projected metadata/flags without treating the file as executable instructions or allowing it to authorize changes. Keep unsafe free text and credentials excluded. Add export/import roundtrip tests.

### F4 — Medium: setup fingerprint omits relevant configuration fields

**Evidence:** core.digest().

Reproduced a change to an existing hotspot server profile's use-radius field without any change in the setup digest. The selected field list also omits fields such as login-by, html-directory and list-based firewall match selectors. The advertised changed-configuration guard therefore covers only part of the relevant state.

This is not evidence that every omitted field affects every scenario. It is a mismatch between the broad freshness claim and what is checked.

**Required change:** declare dependencies per scenario, fingerprint those fields and revalidate them at apply. Include realistic RouterOS response fixtures and changes to authentication/firewall dependencies.

### F5 — Medium: provider and AI network waits block all owner operations

**Evidence:** server.py holds one global LOCK around every route; payment_worker also holds it while reconciling provider calls. llm_review.py permits a 60-second network timeout.

A slow cloud request can delay refresh, disconnect, ticket actions and other owner requests. Router-owned expiry can still run, but the owner's emergency controls become less responsive. The risk becomes more noticeable over a remote connection.

**Required change:** perform read-only provider/AI calls outside the router mutation lock, use background jobs with bounded state and cancellation, then reacquire a short lock and revalidate location/configuration before applying results. Do not simply remove locking from financial writes.

### F6 — Deployment blocker: prerequisites and compatibility are not automatically established

New-network preflight checks for a spare Ethernet port, some conflicts, global IPv6 disabled and the presence of an input drop rule. The snapshot does not include routing state, and an arbitrary input drop is not proof of a working WAN or adequate WAN forwarding protection. The app also does not configure the selected management service, discover/install missing packages, configure NTP or provide full Wi-Fi provisioning.

These limits are mostly documented. They still mean an ordinary user cannot reliably provide only an IP/password and expect a complete setup. Add a capability/prerequisite screen with observed results, actionable remediation and scenario-specific gates. Certify exact hardware/RouterOS combinations before offering one-click commercial deployment.

## Practicality of each setup

| Setup / capability | Practical assessment | What must be true or change |
|---|---|---|
| Existing MikroTik hotspot, local users | Best first deployment path | Existing WAN, bridge/Wi-Fi, DHCP and hotspot must already work. Validate ticket login, speed limits and expiry on hardware. |
| New paid hotspot | Useful for an isolated guest port, not a whole-router installer | Requires a truly unused Ethernet port, working WAN, verified firewall, IPv6/device-mode prerequisites and portal assets. Default bridged LAN ports will be refused until deliberately prepared. |
| Office internet | Appropriate for an internet-only isolated segment | The planner blocks forwarding to all private/link-local networks and router management. It is unsuitable as-is for an office needing routed access to printers, cameras, an NVR or private servers. Same-subnet Layer 2 traffic is a separate matter. |
| Starlink → MikroTik → external APs | Sensible basic topology for the hotspot pilot | WAN must be configured first. APs must bridge the intended customer segment. The app does not configure TP-Link/Grandstream devices, same-SSID roaming or mesh. |
| TP-Link-only camera network | Outside this product's setup scope | No TP-Link API integration, camera discovery or camera VLAN/NVR access policy. Do not use the guest-isolation scenario as a substitute for a camera-network design. |
| Daily tickets at a power-cycled site | Needs F1 correction and power-cycle tests | Explicitly define behavior for early/late boot, delayed NTP and operation past midnight. |
| Stable-electricity location | Elapsed or fixed business-close policies are clearer | Startup policies need a documented no-reboot fallback; they should not be the default for an always-on business. |
| 3-day, weekly and 28-day access | Elapsed validity is usually the clearer product | Connected-time mode measures accumulated online use, not calendar days. Communicate the sold policy on each ticket. |
| Remote owner control | Works only after network reachability exists | Requires existing VPN/routing or a deliberately reachable encrypted service. No outbound agent, tunnel provisioning, automatic NAT traversal or DNS/DDNS hostname input. |
| User Manager | Useful configuration editor and walkthrough | Not a complete commercial RADIUS lifecycle. Install matching package first and test NAS/client secret, accounting, disconnect reachability and licence capacity. |
| Payments | Attended checkout/issuance pilot | Only the active location is reconciled. Backend must stay running. No public self-service shop, customer delivery or in-app recovery/refund workflow for uncertain paid orders. |
| Sales and archives | Useful operational records after F2 is fixed | Recorded sale status is not proof of router usability; totals are gross recorded amounts, not settlement or profit. |
| AI walkthrough | Useful second opinion with bounded repair execution | Fix F3; keep owner review and do not market partial projections as a complete configuration audit. |
| EXE / DEB | Build infrastructure is in place | DEB previously built/extracted; Windows and installed desktop operation still need acceptance and distribution/signing decisions. |

## User Manager integration gap

The User Manager screen adds users under /user-manager/user. Existing voucher generation writes /ip/hotspot/user. The owner dashboard enriches only local-user records with expiry details, although the session count may include RADIUS sessions. Payment issuance and SQLite inventory continue to follow the local-voucher archive.

A demonstrated User Manager account does not appear as a managed local ticket on the owner dashboard. This is separation by design, not a transport failure, but it prevents a unified User Manager hotspot business workflow. Choose an explicit account backend per location, then connect generation, bulk printing, online purchases, account actions, session history and reporting to that backend. Do not infer local-ticket first-login metadata for RADIUS users.

RouterOS itself distinguishes User Manager users/profiles and depends on NAS accounting for session records. See [MikroTik User Manager documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/2555940/User+Manager).

## Operational and scaling assessment

- **Single active location:** saving many routers does not provide concurrent multi-site operations. Switching away can postpone voucher issuance for paid orders at the previous site.
- **Payment recovery:** at-most-once issuance avoids duplicate tickets, but crashes around issuing can leave orders requiring manual reconciliation. Add a reviewed recovery console linking payment reference, archive, journal and actual router account before live rollout.
- **Retention and growth:** every managed batch gets a dedicated profile; each single-voucher paid order can therefore add another profile. Accounts are retained, the scheduler scans all local users every 30 seconds, and dashboard refresh fetches full tables. Long-running small-router capacity needs measurement and an archive/retention policy. No 100/500-concurrent-user capacity claim is justified by this code review.
- **Network availability:** the universal login-hook NTP guard can deny even connected-time tracked logins before synchronization. That is currently intentional, but it affects availability after a power failure. Make this visible in setup and test actual NTP recovery.
- **Backups:** application JSON backup is not a router backup and excludes payment orders. User Manager has a separate database. A practical recovery plan needs all three stores plus retained recovery journals and a restore drill.
- **Access control:** one shared process token and one OS-account boundary are adequate only for a trusted single owner. Staff accounts, roles and per-device revocation are missing for a commercial multi-operator service.
- **UI:** User Manager is primarily a raw-field editor with written steps. It does not enforce completion of the multi-step RADIUS setup. Add reference dropdowns, typed units, dependency status, connection tests and a complete review page before calling it a wizard for nontechnical owners.
- **Maintainability:** server.py concentrates routes, state, locking and worker behavior. Feature modules help, but explicit service boundaries and shared lifecycle types are needed before adding more business workflows. ROADMAP.md also lags the delivered feature set.

## What is sound

Preserve encrypted transports and certificate pin checks, explicit review/confirmation, location-scoped state, consuming plans before writes, journaling intent, avoiding blind financial retries, redacted User Manager secrets, integer-minor-unit sales records, parameterized SQL, escaped rendering and local router-owned expiry enforcement. These are useful foundations; they need integration tests and real-device evidence rather than replacement with a new language.

## Recommended implementation order

1. Fix F1 and F2, add permanent regressions and verify actual RouterOS script behavior.
2. Fix F3 and F4; narrow freshness claims to tested dependencies.
3. Add a startup capability check for NTP, WAN/routing, services, package/version, firmware features and firewall prerequisites. Split guest hotspot, office LAN and camera/IoT scenarios.
4. Complete a local-user release on one named device/RouterOS combination: login, printing, rates, expiry, cold reboot, interrupted writes, rollback and recovery.
5. Add paid-order recovery and customer ticket delivery; then conduct provider sandbox and controlled live reconciliation tests.
6. Complete the User Manager account backend and RADIUS acceptance flow; keep unsupported operations clearly labeled until done.
7. Isolate external waits from mutation locking, measure growth/remote latency, then validate Windows/DEB distribution and remote operator access.

**Release recommendation:** develop the existing-hotspot/local-user path into the first supported Nelsonict product. Keep new-network automation, User Manager and unattended payments marked experimental until their applicable gates pass. This review records findings; it does not change application behavior or fix the defects above.

## Primary references consulted

- [MikroTik Hotspot](https://help.mikrotik.com/docs/spaces/ROS/pages/56459266/HotSpot+-+Captive+portal): service behavior and hotspot configuration context.
- [MikroTik User Manager](https://help.mikrotik.com/docs/spaces/ROS/pages/2555940/User+Manager): package, profile, NAS and accounting model.
- [MikroTik NTP](https://help.mikrotik.com/docs/spaces/ROS/pages/40992869/NTP): synchronized clock status.
- [MikroTik Files](https://help.mikrotik.com/docs/spaces/ROS/pages/2555971/Files): copy operations and flash/power-loss considerations.

The documentation pages identify themselves as frozen and point to the newer manual. They support API/design context, not certification of the requested RouterOS 7.24.2 release.
