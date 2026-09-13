# Application backup and restore

Open **Connection guide → Backup & restore application data**.

1. Select **Download backup**. Keep the JSON file privately: it contains readable voucher passwords, profile prices, templates, the SQLite sales ledger and saved location settings. Router management passwords, Paystack keys, payment orders and router configuration are excluded.
2. To restore, select a backup JSON file. Use the migration editor to review saved connection settings, confirm the old backend is stopped, and select **Review restore with these settings**. Review the file count, groups, replacements and connection changes.
3. Disconnect the router, then select **Restore reviewed backup** and confirm RESTORE. The backend saves a recovery copy under `data/recovery` before writing. Existing files absent from the backup remain; matching files are replaced, not merged record by record.
4. Reload saved locations and templates, reconnect the router, and check prices and voucher history. Restoration changes local data only; it does not recreate router accounts, reset expiry, activate templates on the router or issue paid orders.

Backups include saved location IDs so their archives remain associated with those locations. The imported data replaces matching whole files, so an older backup can hide newer archived vouchers or prices; the recovery copy contains the prior local data. Select that recovery JSON through the same restore interface if needed.

The importer validates supported paths and record structures, rejects path traversal and symlink destinations, and accepts at most 2,000 files and 12 MB of JSON data. Files use atomic replacements. A handled write failure attempts to restore affected prior files. A process crash or power loss during a multi-file restore can leave partial state; use the saved recovery copy after resolving the cause. Backups are not encrypted at rest. For full disaster recovery, also preserve the payment ledger and router backups separately as described in PAYMENTS.md.


Sales inventory and correction history are exported as validated rows under the logical backup entry `sales/ledger.json`; raw SQL is never executed from a backup. Restoration transactionally replaces the sales ledger while retaining the automatic pre-restore recovery copy. Payment orders remain excluded. After reconnecting, issued payment orders still present in the payment store are indexed idempotently when reports are loaded. Missing newer cash entries cannot be reconstructed from voucher credentials, so use the recovery copy or a current backup.

## Moving to another computer with the GUI

1. On the old computer, download an application backup from **Connection guide → Backup & restore application data**. Stop the old backend before switching operations. If you need payment orders and change journals, preserve and transfer the stopped complete data folder separately; the JSON backup excludes these records.
2. Install and start the app on the new Windows, Linux or macOS computer. Open its own launch URL, leave the router disconnected, and select the backup JSON in Connection guide.
3. In **Move to another computer**, edit each saved location's name, router IPv4 address, username, API/REST service, port and optional independently verified certificate fingerprint. Changing the service fills its default port; enter a custom port afterward if needed.
4. Review the destination data folder and the presence of payment/AI environment settings. Values and secrets are not shown. Configure required environment variables on the new computer and restart before using those integrations. A configured indicator is not a validity test. HTTPS certificates, backend listen address, firewall and VPN access need configuring separately for the new host.
5. Confirm the old backend is stopped and the locations refer to the original MikroTik routers. Select **Review restore with these settings**. Any subsequent edit invalidates the preview. Inspect before/after settings and file replacements, then restore with `RESTORE`.
6. Open Connect your router, select a restored location and enter its password. Saved locations reload after restore. Check prices, archives, sales, NTP, expiry automation and the chosen printer before resuming sales. Reload template/report views to discard previously displayed data.

The editor preserves location IDs and does not remap prices, voucher archives or sales to another router. Records remain scoped by location ID and the existing RouterOS identity. A changed connection IP can therefore retain access to saved-location records when the router identity is unchanged. Manual-connection archives still require their original IP and identity; automatic scope migration is not implemented. Renaming a location's display label does not change the router identity.

This is application migration between computers, not a MikroTik hardware restore. Replacing or resetting a router requires separate RouterOS/User Manager backups and reconciliation of accounts before archived vouchers are used. The GUI does not recreate users, import payment orders, reconfigure host networking, save router passwords or provision cloud secrets. Existing restore path validation, recovery copies, disconnected-only writes and backup size limits apply to migration too.
