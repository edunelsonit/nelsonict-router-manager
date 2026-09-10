# Payments and automatic voucher issuance

This pilot integrates **Paystack hosted checkout** with owner-created purchase links and automatic voucher issuance. It supports positive NGN profile prices and one voucher per transaction. It has not been tested against a live Paystack merchant or real MikroTik router.

## Enable and use

1. Create/configure your Paystack merchant account. Start with its test secret key. Set `PAYSTACK_SECRET_KEY` in the environment of the Python backend process, then restart the app. Do not put keys in GitHub, templates, browser code or chat messages. On Linux/macOS use your environment/secrets configuration; on Windows set the process environment before starting Python. Test keys begin `sk_test_`; live keys begin `sk_live_`.
2. Connect the backend to the intended router/location. Save a positive NGN price for its user profile. Install and verify expiry automation if selling tracked tickets.
3. In Vouchers & users, select the profile, hotspot server, duration, credential type and expiry settings. Under **Pay & receive a voucher**, enter the customer's email and select **Create checkout link**. Each link purchases one voucher, regardless of the normal batch-count field. The order snapshots its price and settings.
4. Share the hosted Paystack checkout link with the customer. Customers enter payment details on Paystack; they must not receive the private owner launch URL. The customer needs internet access for checkout; this release does not modify walled-garden settings.
5. Keep the Python backend running with that location connected. A background worker checks pending orders every 30 seconds, processing up to three per pass. Verification traffic may extend the interval. The browser can be closed. Switching locations pauses processing for the previous location until reconnected.
6. Use **Check payments** to refresh results or trigger verification immediately. A verified payment automatically creates one voucher, which appears under **Saved vouchers** for preview, printing or owner-managed sharing. Test-mode vouchers are labelled TEST PAYMENT on the ticket price line.

## Verification and interruption handling

The backend verifies transactions directly with Paystack. It requires success, the exact order reference, amount in kobo, currency, customer email and test/live mode. Browser redirects and customer claims never authorize issuance. Order storage is scoped to the current location/router identity and the original key fingerprint; changing keys prevents that key from processing older orders. One Paystack merchant key is configured per backend process.

The backend persists an issuance intent before writing to the router. `issued` orders are never issued again automatically. `issuing` after a crash, `needs-review`, or `verification-mismatch` require operator investigation. Search the voucher archive using the payment reference and inspect the router/change journal before manually replacing a ticket. This provides at-most-once automatic attempts, not a distributed transaction or an unconditional delivery guarantee. No automatic retries of uncertain router writes occur.

Profile configuration changes, missing expiry automation, unsynchronized time, expired fixed deadlines, disconnected routers or disk errors may leave a successful payment needing review. Resolve delivery or a refund through the merchant's normal process. Refunds, reversals, disputes and automated voucher revocation are not implemented. Test the complete process before switching to a live secret key.

`data/payments` contains orders and issuance state, with restrictive file permissions. Keep it intact to prevent loss of payment history. The application backup tool intentionally excludes this ledger and never restores or rewinds paid-order state. For a full backend migration, stop all instances and move the entire private data directory separately; never run two copies that could process the same orders. The app does not support concurrent backend processes sharing a data folder.

## Current limits

There is no public storefront, unattended captive-portal purchase UI, SMS/email voucher delivery, multi-merchant routing or webhook endpoint. Hosted checkout links can be shared with customers, and voucher creation is automatic after server verification, but the owner currently delivers the resulting credentials. Do not expose the management API publicly to work around this limitation.

References: [Paystack transactions API](https://paystack.com/docs/api/transaction/) and [payment verification guidance](https://paystack.com/docs/payments/verify-payments/).
