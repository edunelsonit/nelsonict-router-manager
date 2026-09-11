# AI setup walkthrough

Open **AI walkthrough** after connecting to a router, or use demonstration mode. Local diagnosis and repairs work without an AI account.

1. Collect a read-only API snapshot. Leave profile and batch blank to inspect all tickets, or narrow the review. Unavailable menus are listed. Download the projected JSON for later review.
2. Alternatively, import a JSON snapshot or textual RouterOS `.rsc` export (maximum 256 KB). The RSC reader extracts supported configuration fields only; unsupported lines are omitted. It never executes imported scripts. Imported evidence is read-only and cannot authorize router writes. This is a partial diagnostic projection, not a complete RouterOS export or backup.
3. Inspect the evidence. For optional AI analysis, configure `OPENAI_API_KEY` and `OPENAI_MODEL` in the server process environment before launch. Choose an OpenAI model supporting the Responses API and structured outputs. Never put the key in router comments or browser files. Confirm the sharing checkbox, then request analysis.
4. Review recommendations and each selected repair's exact before/after values. Keep a separate router backup, confirm the backup checkbox, and type `APPLY FIXES` in the confirmation dialog.
5. Collect a fresh snapshot after applying. Some repairs depend on restored expiry automation and therefore require a second review.

## Supported repairs

- Normalize valid managed ticket comments while retaining the existing policy, first-login timestamp and deadline.
- Align uptime limits with existing policies. Calendar-policy repairs that would remove a limit require verified automation and usable activation metadata.
- Disable expired tickets and remove their active sessions and cookies.
- Restore the bundled expiry scheduler only when its application ownership is verified and router time is trusted.
- Restore a missing login hook on a verified managed batch profile without replacing custom hooks.

Use **Select all repairs** for a bulk operation. Reviews are limited to 1,000 repairs; narrow the profile or batch filter for larger installations. Lost activation dates, damaged policy metadata, uncertain clocks, foreign scripts and firewall changes require manual review. AI cannot reliably reconstruct missing dates or fix every possible setup fault. Install a missing expiry engine through the existing voucher engine installer.

## Ticket comments

The ticket table allows selecting ordinary legacy comments and previewing a replacement for all selected accounts. Check whether external legacy automation uses those comments before replacing them. Managed `ns2` and `ns-batch-` comments are protected because they contain expiry/archive metadata. Valid managed comments can be normalized through the repair list; arbitrary notes cannot replace them. Batch filtering scopes policy repairs; the legacy comment table is scoped by profile and explicit account selection.

## Data sharing and execution

The owner can inspect real ticket names and comments locally. AI receives an allowlisted projection: ticket names become aliases; passwords, free-form comments and script bodies are omitted. Interface/profile names, network addresses and selected configuration fields remain visible, so inspect the projection before sharing. Do not place secrets in configuration names. Only the reviewed projection is sent to OpenAI, using `store: false`; this setting is not a promise of zero provider retention. See [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

The model returns findings and identifiers of server-generated supported fixes. It cannot supply executable RouterOS commands. Live plans expire after ten minutes, are tied to the active location and are consumed before writes. The server checks fresh configuration and each target's original fields to reject stale changes. A failed or uncertain operation requires recollection, not a blind retry.

Change history records intent and before/after values before mutation. Repair journals are not automatically reversible: restoring an expired account or recreating disconnected sessions would be unsafe. Use the retained journal and router backup for deliberate manual recovery. Application backups do not replace router backups.

Automated tests use a simulated router and mocked AI responses. Real RouterOS hardware, browser interaction and live model calls still require acceptance testing.
