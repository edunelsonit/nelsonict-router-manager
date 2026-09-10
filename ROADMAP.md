# Product roadmap

## Delivered pilot

Local single-router connection, HTTPS with CA validation or explicit certificate pinning, three additive scenarios, plan review, preflight conflict checks, connected-time vouchers, print/CSV, account status and disable cleanup, simulated demo, persistent write journal and limited rollback.

## Next: tested RouterOS release

Run ACCEPTANCE.md on hAP ax2 and a second RouterOS architecture at the requested version. Resolve device-mode, hotspot portal file provisioning, firewall ordering and firmware-specific response differences. Add version/capability fixtures from sanitized real responses. Package signed Windows/macOS launchers once verified.

## Implemented in v0.2; hardware acceptance pending

Five per-batch expiry policies, router login hooks and scheduler, persistent activation/deadlines, owner dashboard with expired-active alerts, any-local-ticket controls, and optional HTTPS mobile web access. Validate RouterOS execution, timing, permissions and power-cycle persistence against EXPIRY.md and ACCEPTANCE.md before calling the release production-ready.

Native mobile packaging, independently revocable device tokens, app-store delivery, push notifications and a hosted outbound agent remain future work.

## Broader setup scenarios

Versioned, tested templates for Starlink WAN setup, bridged Grandstream access points, Wi-Fi/qcom interface discovery, VLANs, PPPoE server, DHCP/static/PPPoE WAN, dual-WAN failover and schools/hotels. Add migration only after inspecting each existing installation. Templates must declare prerequisites, conflicts and recovery steps.

## Commercial platform

Operator roles, multiple routers, encrypted credential storage with OS keychain support, tamper-evident audit records, validated payment/revenue workflows, hosted control plane with an outbound authenticated local agent, backups and monitoring. Existing architecture is not advertised as ready for untrusted remote users.
