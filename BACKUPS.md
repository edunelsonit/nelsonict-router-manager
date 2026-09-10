# Application backup and restore

Open **Connection guide → Backup & restore application data**.

1. Select **Download backup**. Keep the JSON file privately: it contains readable voucher passwords, profile prices, templates and saved location settings. Router management passwords, Paystack keys, payment orders and router configuration are excluded.
2. To restore, select a backup JSON file. Review its file count, groups and number of files that will be replaced.
3. Disconnect the router, then select **Restore reviewed backup** and confirm RESTORE. The backend saves a recovery copy under `data/recovery` before writing. Existing files absent from the backup remain; matching files are replaced, not merged record by record.
4. Reload saved locations and templates, reconnect the router, and check prices and voucher history. Restoration changes local data only; it does not recreate router accounts, reset expiry, activate templates on the router or issue paid orders.

Backups include saved location IDs so their archives remain associated with those locations. The imported data replaces matching whole files, so an older backup can hide newer archived vouchers or prices; the recovery copy contains the prior local data. Select that recovery JSON through the same restore interface if needed.

The importer validates supported paths and record structures, rejects path traversal and symlink destinations, and accepts at most 2,000 files and 12 MB of JSON data. Files use atomic replacements. A handled write failure attempts to restore affected prior files. A process crash or power loss during a multi-file restore can leave partial state; use the saved recovery copy after resolving the cause. Backups are not encrypted at rest. For full disaster recovery, also preserve the payment ledger and router backups separately as described in PAYMENTS.md.
