# Payments and automatic voucher issuance

This pilot integrates **Paystack, Monnify and Flutterwave hosted checkout** with owner-created purchase links and automatic voucher issuance. It supports positive NGN profile prices and one voucher per transaction. It has not been tested against live merchant accounts or real MikroTik router.

## Enable and use

1. Create/configure your Paystack merchant account. Start with its test secret key. Set `PAYSTACK_SECRET_KEY` in the environment of the Python backend process, then restart the app. Do not put keys in GitHub, templates, browser code or chat messages. On Linux/macOS use your environment/secrets configuration; on Windows set the process environment before starting Python. Test keys begin `sk_test_`; live keys begin `sk_live_`.
2. Connect the backend to the intended router/location. Save a positive NGN price for its user profile. Install and verify expiry automation if selling tracked tickets.
3. In Vouchers & users, select the profile, hotspot server, duration, credential type and expiry settings. Under **Pay & receive a voucher**, select a payment provider, enter the customer's email (and name for Monnify) and select **Create checkout link**. Each link purchases one voucher, regardless of the normal batch-count field. The order snapshots its price and settings.
4. Share the hosted provider checkout link with the customer. Customers enter payment details on the provider checkout page; they must not receive the private owner launch URL. The customer needs internet access for checkout; this release does not modify walled-garden settings.
5. Keep the Python backend running with that location connected. A background worker checks pending orders every 30 seconds, processing up to three per pass. Verification traffic may extend the interval. The browser can be closed. Switching locations pauses processing for the previous location until reconnected.
6. Use **Check payments** to refresh results or trigger verification immediately. A verified payment automatically creates one voucher, which appears under **Saved vouchers** for preview, printing or owner-managed sharing. Test-mode vouchers are labelled TEST PAYMENT on the ticket price line.

## Verification and interruption handling

The backend verifies transactions directly with the selected provider. It requires success, the exact order reference, amount in kobo, currency, customer email and test/live mode. Browser redirects and customer claims never authorize issuance. Order storage is scoped to the current location/router identity and the original key fingerprint; changing keys prevents that key from processing older orders. One merchant configuration per provider is supported per backend process. Legacy orders without a provider field remain Paystack orders.

The backend persists an issuance intent before writing to the router. `issued` orders are never issued again automatically. `issuing` after a crash, `needs-review`, or `verification-mismatch` require operator investigation. Search the voucher archive using the payment reference and inspect the router/change journal before manually replacing a ticket. This provides at-most-once automatic attempts, not a distributed transaction or an unconditional delivery guarantee. No automatic retries of uncertain router writes occur.

Profile configuration changes, missing expiry automation, unsynchronized time, expired fixed deadlines, disconnected routers or disk errors may leave a successful payment needing review. Resolve delivery or a refund through the merchant's normal process. Refunds, reversals, disputes and automated voucher revocation are not implemented. Test the complete process before switching to a live secret key.

`data/payments` contains orders and issuance state, with restrictive file permissions. Keep it intact to prevent loss of payment history. The application backup tool intentionally excludes this ledger and never restores or rewinds paid-order state. For a full backend migration, stop all instances and move the entire private data directory separately; never run two copies that could process the same orders. The app does not support concurrent backend processes sharing a data folder.

## Current limits

There is no public storefront, unattended captive-portal purchase UI, SMS/email voucher delivery, multi-merchant routing or webhook endpoint. Hosted checkout links can be shared with customers, and voucher creation is automatic after server verification, but the owner currently delivers the resulting credentials. Do not expose the management API publicly to work around this limitation.

References: [Paystack transactions API](https://paystack.com/docs/api/transaction/) and [payment verification guidance](https://paystack.com/docs/payments/verify-payments/).


## Monnify and Flutterwave setup

Choose the provider under Vouchers & users → Pay & receive a voucher. Configure these environment variables on the backend and restart it:

| Provider | Required variables | Mode |
|---|---|---|
| Paystack | `PAYSTACK_SECRET_KEY` | `sk_test_` or `sk_live_` prefix |
| Flutterwave v3 | `FLUTTERWAVE_SECRET_KEY`, `FLUTTERWAVE_REDIRECT_URL` | `FLWSECK_TEST-` or `FLWSECK-` prefix |
| Monnify | `MONNIFY_API_KEY`, `MONNIFY_SECRET_KEY`, `MONNIFY_CONTRACT_CODE`, `MONNIFY_REDIRECT_URL` | `MONNIFY_MODE=test` (default) or `live` |

Flutterwave uses v3 Standard hosted payments and verification by `tx_ref`, not v4 OAuth. Monnify uses server-side token authentication and transaction initialization, then verifies the returned transaction reference. Monnify sandbox uses `sandbox.monnify.com`; live uses `api.monnify.com`. Customer name is required for Monnify.

Redirect URLs must be HTTPS receipt/instruction pages you control, not the private owner launch URL. No receipt page is deployed by this update. Redirects never authorize issuance; only authenticated backend verification does. Customers still receive vouchers through the owner; SMS/email delivery and a public storefront are not included.

Flutterwave and Monnify checkout amounts use naira; verification normalizes to integer kobo. Flutterwave must return successful; Monnify must return PAID. Reference, currency, email and exact amount must match. Test/live separation for these providers is bound to the verification key or sandbox endpoint. Changing keys, contract code or mode prevents the new configuration from processing old orders. Monnify initialization interrupted before saving its provider transaction reference requires merchant-dashboard reconciliation.

Start in sandbox. Verify actual response fields and hosted checkout domains, partial payments and fee arrangements: a Monnify amount-paid value differing from the advertised price is not automatically reconciled. Mocked tests passed, but neither provider's sandbox nor live merchant account was tested. Documentation access was incomplete in this environment; unsupported response formats fail without issuing vouchers. Test checkout, abandoned/failed payments, duplicates, mismatches and interrupted router delivery before live use.

References: [Monnify API](https://developers.monnify.com/api), [Flutterwave verification by reference](https://developer.flutterwave.com/v3.0/reference/verify-transaction-with-tx_ref).
