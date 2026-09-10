# Hardware acceptance checklist

Status: **not executed on a real router**. Use a spare router or isolated lab with a backup and physical access. Record the exact RouterOS version, architecture, hardware, package versions, test date and results. Do not present 7.24.2 as certified until every applicable test passes.

1. Verify the requested RouterOS release through MikroTik, then install it and appropriate Wi-Fi packages using its official procedure.
2. Connect using trusted-CA HTTPS; test wrong passwords, missing REST policy, blocked port and wrong certificate pin. Confirm all fail without configuration writes.
3. Verify simulated mode never writes to the live router and disconnect clears the live session.
4. Existing hotspot: create a new profile, verify rate-limit direction, one-user sharing and RADIUS independence, then generate and log in with vouchers.
5. New hotspot: use a spare Ethernet port, enabled Hotspot device-mode, disabled global IPv6, verified WAN firewall, default hotspot files and no active FastTrack. Confirm plan menu/property compatibility, dynamic rule ordering and portal file availability.
6. Before authorizing a guest, confirm it receives DHCP, reaches the login page, resolves required names and cannot browse the internet or access router management/private networks.
7. After login, confirm internet, DNS, bandwidth caps and continued management isolation. Validate protections with the router's real firewall/NAT order, default drops and upstream topology. Check client-to-client isolation separately on the external AP.
8. Office scenario: verify DHCP, DNS, internet and guest-to-management isolation. Confirm WAN and existing LAN users are unaffected.
9. Create a short disposable voucher with a small allowance in WinBox, then confirm RouterOS ends access after consuming the connected-time limit even when the app is stopped. Check power-cycle persistence. Also execute the v0.2 tests below.
10. Test MAC randomization and stale sessions; document re-login behavior. Confirm disable retains the account and removes active sessions and cookies.
11. Interrupt a write deliberately in the lab. Verify uncertain records stop the batch, no automatic retry occurs, and the operator can reconcile in WinBox.
12. Roll back a fresh setup and voucher batch. Verify only recorded additions are removed. Test rollback refusal after editing a created object. Test reconnect after app restart and local journal permissions.
13. Check application startup and browser behavior on actual Windows, Ubuntu and macOS. Confirm no third-party dependency download is required.
14. Record a production decision only after the above pass. A generated plan is not proof that every command is accepted or every firewall policy is correct on every router.

## v0.2 release gates (not yet executed on hardware)

15. Install the scheduler with the documented account; confirm interval/run-count, permissions, no router log errors and hook invocation after successful hotspot login.
16. Verify first login is stored once, remains unchanged on reconnect and survives router/app restarts. Older accounts must remain unknown. Test connected tickets first used while NTP is unavailable.
17. Exercise all five policies, same-day reboot, later-day reboot, no reboot, multiple reboots, unused tickets and fixed expiry before use. Check offset boundaries and closing-time equality.
18. Delay NTP past boot +10 minutes, then synchronize; confirm no extra grace is granted. Verify active calendar sessions are removed during unverified time, and restored clock alone does not re-enable expired users.
19. Confirm elapsed/fixed/native deadlines and connected-time limits work with the Python app completely stopped. Measure the expected 30-second polling tolerance.
20. Disable automation deliberately in the lab and demonstrate the dashboard's expired-active alert and manual cleanup. Inspect malformed policy and custom-profile rejection behavior.
21. On a real phone, validate trusted HTTPS, wrong Origin/token rejection, private-IP binding, refresh timestamps, search/filter, disable cleanup and protected enable. Validate certificate SANs and firewall isolation from customers.
22. Check native scripts directly on the requested RouterOS version. Python evaluator tests do not prove RouterOS syntax, policy permissions or actual execution.
