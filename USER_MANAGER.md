# User Manager and remote control

Open **Remote control** to prepare a connection to another site's IPv4 address using API-SSL or HTTPS REST. The application uses its existing router transport and certificate checks, then all owner actions operate on that connected router. Save the connection under a location to switch sites. Passwords remain session-only. A routed management VPN must already be working, or the remote encrypted service must be reachable through configured inbound access. The app does not create VPN tunnels, NAT forwarding or firewall openings. Starlink behind carrier NAT generally requires an outbound VPN solution. Phone-to-backend access uses the HTTPS mode in [MOBILE.md](MOBILE.md).

## Before User Manager setup

Install the user-manager package matching the router's installed RouterOS version and architecture through your normal maintenance process. Confirm licence capacity, free storage, synchronized time and permission to access User Manager over the selected API service. Package installation, reboot and licence changes are not performed by this application. Keep separate RouterOS and User Manager database backups; the app's JSON backup does not back up the router's User Manager database.

The **User Manager** page provides settings and create/update/delete controls for RADIUS router clients, profiles, limitations, profile-limit links, users, authentication groups and user-profile assignments. It can configure the connected router's RADIUS client and enable RADIUS/accounting on a selected existing Hotspot server profile. Session, payment and database information is read-only. Search narrows records; records are sorted by name/user/ID. Secrets are never shown in lists or review journals.

## Hotspot and User Manager on the same router

Load User Manager, select each configuration area, enter values, preview, apply and refresh before the next step. **Fill suggested setup values** supplies starter values for common sections; inspect them before use.

1. Service settings: enabled=yes and use-profiles=yes.
2. RADIUS router clients: name=local-hotspot, address=127.0.0.1, protocol=udp, coa-port=3799, and a strong shared-secret.
3. Router RADIUS client: address=127.0.0.1, service=hotspot, the identical secret, authentication-port=1812, accounting-port=1813 and timeout=1s. Do not add duplicate clients to an already configured installation.
4. Hotspot RADIUS integration: select the actual server profile, set use-radius=yes, radius-accounting=yes and radius-interim-update=1m. Every hotspot server sharing that profile is affected.
5. Incoming disconnect requests: first restrict access to trusted RADIUS servers using the site's firewall, then set accept=yes and port=3799. Match the router client's CoA port. Firewall changes are not automatic.
6. Create a named profile, for example daily, validity=1d, starts-when=first-auth, price=500 and override-shared-users=1. Use 3d, 7d or 28d for other elapsed-validity plans.
7. Create a limitation with upload/download rates or uptime/data allowances, then link its name and the profile name under Profile limit assignments. Rate RX is upload from the customer; TX is download. Data quotas are in bytes.
8. Create a user and password; for PIN login use the same value in both fields. Assign a profile under User profile assignments. A user without an assignment will not have the intended profile entitlement.
9. Test one login, verify accounting/session records and expiry, then provision additional accounts. Conflicting local Hotspot usernames can take precedence over RADIUS users.

For a separate User Manager server, configure the NAS router's address on the User Manager server, and the server's reachable address on the NAS RADIUS client. Use a protected routed network and matched secrets. Switch saved locations to configure each device separately. Loopback defaults are for a co-located installation only.

These controls follow the [RouterOS User Manager menus](https://help.mikrotik.com/docs/spaces/ROS/pages/2555940/User+Manager). Verify behavior on your exact RouterOS version.

## Change review and recovery

Only documented, allowlisted menus/fields are accepted. RouterOS validates their detailed service rules. Blank fields are omitted; edit a nonblank value to change it. Select a row for updates/deletion; singleton settings cannot be created or deleted. Missing references and duplicate names are rejected before creation.

Plans remain in memory for ten minutes, are bound to the active location and checked against fresh configuration. Confirmation requires a backup acknowledgment and APPLY USER MANAGER. A consumed or uncertain plan cannot be retried. Change history records redacted intent before writes and checks nonsecret field readback afterward. These records have no automatic rollback. Refresh and inspect the router after failures. Disabling a user blocks authentication but is not a guarantee of immediate disconnection of existing remote NAS sessions.

## Scope

This is configuration support for RouterOS v7 User Manager, not complete parity with every RouterOS command. Native package/database maintenance, custom RADIUS attribute definitions, certificate provisioning, remote NAS session termination, legacy migration and User Manager batch printing are not implemented. Existing local-hotspot voucher generation, next-day-startup expiry, archives, payment issuance and SQLite sales reporting remain separate and do not automatically apply to User Manager users. User Manager price fields are router metadata and do not link the application's payment providers to RADIUS accounts. No lost activation dates are inferred.

Validation uses simulated routers and mocked transport; real hardware, RADIUS authentication/accounting, remote connectivity and browser interaction remain acceptance requirements.
