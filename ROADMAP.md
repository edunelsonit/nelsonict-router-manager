# Product roadmap

## Delivered pilot

Local single-router connection, HTTPS with CA validation or explicit certificate pinning, three additive scenarios, plan review, preflight conflict checks, connected-time vouchers, print/CSV, account status and disable cleanup, simulated demo, persistent write journal and limited rollback.

## Next: tested RouterOS release

Run ACCEPTANCE.md on hAP ax2 and a second RouterOS architecture at the requested version. Resolve device-mode, hotspot portal file provisioning, firewall ordering and firmware-specific response differences. Add version/capability fixtures from sanitized real responses. Package signed Windows/macOS launchers once verified.

## Ticket-expiry engine

Implement 1d/3d/7d/28d elapsed validity from first login and a separate business-day rule: eligible prior-day tickets expire 10 minutes after the next day's router boot, only after a trusted clock is available. Persist activation and expiry across power loss, preserve account records, revoke sessions/cookies and distinguish a same-day reboot from next-day opening. Test delayed NTP, power failure during state write, multiple reboots, no reboot, clock moving backward, unused tickets and random MAC changes. Never approximate these policies with limit-uptime.

## Broader setup scenarios

Versioned, tested templates for Starlink WAN setup, bridged Grandstream access points, Wi-Fi/qcom interface discovery, VLANs, PPPoE server, DHCP/static/PPPoE WAN, dual-WAN failover and schools/hotels. Add migration only after inspecting each existing installation. Templates must declare prerequisites, conflicts and recovery steps.

## Commercial platform

Operator roles, multiple routers, encrypted credential storage with OS keychain support, tamper-evident audit records, validated payment/revenue workflows, hosted control plane with an outbound authenticated local agent, backups and monitoring. Existing architecture is not advertised as ready for untrusted remote users.
