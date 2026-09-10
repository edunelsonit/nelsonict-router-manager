# Owner dashboard on a phone

Version 0.2 adds a responsive **mobile web dashboard**, served by the existing Python backend. It is not yet a native Android/iOS package or cloud service.

## What the owner can do

- See distinct connected usernames and the number of active sessions.
- See router-recorded first login for new tracked tickets, separate from an estimated current-session start.
- Search tickets and filter online, expired, expired-but-connected and disabled accounts.
- Disable any local hotspot account, retaining the account record while removing sessions and cookies.
- Disconnect sessions without disabling a valid ticket.
- Re-enable a ticket only when its known expiry allows it. Re-enabling never extends validity.
- Generate and print/export vouchers through the same responsive interface.

The dashboard refreshes every 15 seconds while visible, with a last-refreshed timestamp and an explicit stale-data message on polling failure. It is a sampled snapshot, not continuous telemetry. Counts include authenticated sessions reported by RouterOS; RADIUS-only users can contribute to counts but are not editable local accounts.

## Secure phone access over LAN or a management VPN

1. Keep the backend computer running on a trusted network and able to reach the router. Give it a stable private IPv4 address. Do not place it on the untrusted customer hotspot segment.
2. Obtain a TLS server certificate and private key for that computer's private IP. The certificate must contain the IP in its subject alternative name, and the issuing CA must be trusted by the phone. Use your organization's certificate provisioning process; do not bypass certificate warnings.
3. Save the PEM certificate and private key outside the source repository, with access limited to the OS account running the server.
4. Start, replacing the example address and paths:

   ```sh
   python3 server.py --listen 192.168.10.20 --port 8765 --tls-cert /private/server.crt --tls-key /private/server.key --no-browser
   ```

   Windows supports the same flags with `py -3` and Windows paths.
5. Restrict the computer firewall to the owner's device or management VPN subnet. Do not forward this port from the public internet.
6. Open the exact **private launch URL** printed by the application on the phone. It includes an owner access token after `#token=`. Use a private, trusted channel to transfer it. This token permits all owner operations; protect it like a password.
7. Connect the router in the interface, or use the connection already established from another authorized owner tab. All owner tabs share one active router. Disconnecting clears that shared connection.
8. Open **Owner dashboard**. Optional: add a browser home-screen shortcut. Browser shortcut installation and native push notifications are not implemented.

The server refuses `0.0.0.0`, public bind addresses and non-loopback HTTP. It accepts only the exact configured Host and Origin plus the per-process access token. Restarting the process rotates the token, requiring a fresh launch link on each owner device. The default `python3 server.py` remains loopback-only HTTP.

For access away from the site, first connect the phone to an existing management VPN that can reach the backend computer. This release does not set up that VPN. If Starlink or another uplink uses NAT, the computer still needs a reachable VPN route; a router's LAN IP is not directly reachable over the public internet.

## Future native mobile client

The JSON endpoints in API.md form the starting point. A native app will additionally need independently revocable device credentials, user accounts/roles, pairing, device-key storage, connection lifecycle, background polling/push notifications and a secure remote agent or VPN. This release's shared owner token is intentionally not a multi-user SaaS authentication system.
