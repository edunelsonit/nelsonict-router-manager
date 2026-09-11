# Sales reports and voucher tracking

The Sales reports screen combines a sale ledger with inventory from confirmed archived vouchers. Generating or using a voucher is not evidence of a sale.

## Record and review

1. Connect to the desired saved location or manual router context, then open Sales reports.
2. Choose Daily or Monthly, dates, profile and UTC offset. Nigeria uses +60 minutes. The report groups by period, profile and currency, keeping different currencies separate. Export report CSV downloads these totals.
3. In inventory, filter by sold/unsold, profile, exact batch ID or username. Inventory filters apply to confirmed vouchers currently available in the archive, independent of the report date range. Large results use pages of 100.
4. For a cash sale, choose Record cash sale and enter the actual amount/currency received. A saved voucher price pre-fills the form. Unpriced/recovered vouchers require an explicit amount. Zero is allowed for complimentary vouchers. Cash sales are timestamped when recorded; historical cash sales are not automatically backdated.
5. Correct an erroneous cash sale using Correct to unsold. The original ledger entry remains with a void timestamp; it is excluded from totals. This restates the original report period. It is a recording correction, not a provider refund or account action.

## Status and reporting meaning

- **Unsold:** no active sale recorded. Historical cash sales may exist outside the app. Enter them deliberately; never infer sale from first login, expiry or generation.
- **Sold:** active cash entry or verified, issued live-provider order linked to the voucher.
- **Payment pending/review:** voucher has a payment reference but no confirmed issued sale. This cannot be converted to a cash sale using the controls.
- **Test:** a test payment voucher; excluded from sales totals and cash recording.

Online orders are indexed idempotently when reports load. New orders use successful issuance time. Older orders use verification time if present, otherwise order creation time; these fallback dates may differ from the actual payment date. Reports count fulfilled recorded sales, not all money received by the provider. Provider dashboards remain the source for settlement, fees, disputed charges and refunds.

Sold vouchers may be unused, expired, disabled or deleted on the router. Sale controls do not modify router accounts, passwords, expiry or printed ticket prices. Gross totals exclude voided cash entries and test payments but do not deduct provider fees or refunds. A price change affects future vouchers, not an existing sale.

## SQLite and data continuity

`data/sales.sqlite3` uses Python's built-in sqlite3 module, schema version 1, foreign keys, lookup indexes and a unique constraint allowing one active sale per voucher. Money is integer minor units. Cash insertion uses an immediate transaction; corrections retain audit rows. The database stores usernames, batch/profile metadata, amounts, payment references and timestamps, with no voucher or router passwords.

Existing JSON archives and payment orders remain authoritative for issuance. Their confirmed records are indexed automatically; manual sale state survives restarts in SQLite. Locations are isolated using the saved location ID/manual address plus router identity. Demo sales use a separate in-memory SQLite database and reset with demo mode.

Backups include structured sales rows and restore them transactionally, alongside the existing application data. Never copy a live SQLite file as a substitute for the application backup. Stop the app before a full raw-directory migration, and preserve the payment order store separately. One backend process per data directory is supported. Removing or restoring an archive does not erase recorded sale history; inventory availability and historical reports can therefore differ.

No staff identity/audit attribution is available in the current single-owner authentication model. Multi-user permissions, provider refunds, commissions, expenses and profit reports remain future work.
