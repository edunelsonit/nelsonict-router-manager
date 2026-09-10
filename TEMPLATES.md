# Voucher template editor and portal installation

Version 0.3 separates **printed appearance**, **credential generation**, and **the customer login page**. Changing a printed template never changes an existing account's username, password or expiry.

## Create and customize a template

1. Launch the application and open **Template editor**. A router connection is not required for design work.
2. Choose PIN-only or username/password layout. Edit business name, heading, Wi-Fi/network name, colors, price label, contact and footer.
3. Choose A4 with 1–3 columns, or a 58 mm / 80 mm thermal layout. The printer's paper size must match the selected layout; use the browser's print dialog to select it.
4. Choose whether to show validity policy and the user profile. Review the sample voucher in Live print preview.
5. Save to update a selected template, or Save as new to make another design. The built-in default is preserved and saving it creates a copy.
6. Export JSON to transfer the template to another installation. Import JSON previews a copy; save it to retain it.

Templates store branding/settings in `data/templates/`. They do not store ticket passwords or previously generated batches. Editing accepts plain text and validated colors, not arbitrary HTML, JavaScript, external images or RouterOS servlet directives. Logo/image upload, QR codes, drag-and-drop design and arbitrary CSS are not included.

## Generate real credentials

In **Vouchers & users**, choose:

- **PIN only:** 8–16 random digits; default 10. Username and password are identical. PINs begin with a nonzero digit.
- **Separate username/password:** optional prefix (up to 12 safe characters), random username suffix (6–20 characters) and independent random password (8–32 characters). Ambiguous uppercase letters/digits are reduced in the generator alphabet.

Each batch avoids usernames already present on the router and duplicates within the batch. Random generation is cryptographically secure. The app never changes the credentials of existing vouchers just because you switch generation mode.

Choose the print template and the existing expiry policy. After creating the batch, inspect the actual print preview and use Print vouchers or Export CSV. Printing opens the preview frame's print dialog; it does not print the entire management dashboard. If a PIN template is selected for accounts with different passwords, batch printing switches to the two-field layout to avoid hiding a necessary password. A direct API request to render different credentials in PIN-only layout is rejected.

The CSV includes mode, username, password, allowance, policy, profile and batch. Protect CSVs, printed tickets and screenshots. Passwords are returned for the newly created batch and remain in browser memory until the page closes; the app does not save them to template files. Print/export before closing the page. Reprinting historical batches with independent passwords is not implemented.

## Install a matching customer login page

A printed PIN alone does not make the standard MikroTik login page a one-field page.

1. Connect to the router over an enabled API/API-SSL or HTTP/HTTPS REST service.
2. Choose branding and PIN-only or username/password layout in Template editor. Select the hotspot server and click **Prepare direct installation**.
3. Review the previous folder, new unique destination and all servers sharing the profile. The app uses `flash/` when a flash directory exists. Required original support files must be present.
4. Confirm **INSTALL PORTAL**. The app invokes RouterOS `file/copy` to copy the current folder, checks copied file metadata, writes the three generated pages and reads their contents back to verify the upload. Only then does it change the profile's `html-directory`. Authentication methods and existing credentials remain as configured.
5. Test a new customer login. PIN mode requires username=password; use the two-field portal when tickets have independent passwords.
6. To restore, open **Change history** and roll back the portal-deploy record. This restores the prior directory when the profile still matches the installation. It retains both folders. A failed copy/upload leaves the prior portal selected; partially created folders remain for inspection and are never blindly retried or deleted.

The optional ZIP is a three-file overlay, not a complete RouterOS portal. It includes manual installation instructions for advanced use; direct installation does not require WinBox upload. The legacy plan/install API endpoints can still activate an already uploaded folder.

Direct installation requires firmware and permissions supporting directory `file/copy`, file creation and content editing. Unsupported commands stop the installer. Generated pages are limited to 60 KB each. Copy verification checks names/type/size and upload verification checks exact generated text, not binary hashes of original support files. RouterOS flash writeback may be delayed; immediate readback does not guarantee survival of an immediate power cut. Hardware validation of these operations, customer login and reboot persistence remains required.

The portal supports RouterOS **HTTP-CHAP** using the router's existing `md5.js` or **HTTPS** authentication. It refuses unencrypted HTTP-PAP fallback. HTTPS submissions remain on HTTPS. The installer requires a pre-existing compatible authentication method and does not provision captive-portal certificates. Login errors use a generic message rather than reflecting arbitrary submitted credentials.

Use a distinct new directory for later portal updates so directory rollback remains meaningful. The demo simulates directory copying and file uploads; it does not touch a real router.

## API additions

All routes use the existing owner token and Origin checks:

| Endpoint | Purpose |
|---|---|
| `POST /api/templates/list` | List built-in and locally saved templates |
| `POST /api/templates/save` | Validate/save `template`; saving id `default` creates a new ID |
| `POST /api/templates/render` | Return script-free printable HTML for `template`, optionally `vouchers`; without vouchers uses marked samples |
| `POST /api/templates/export` | Return a base64 ZIP and filename for the portal overlay |
| `POST /api/portal/prepare` | Prepare direct installation using `server` and `template` |
| `POST /api/portal/deploy` | Copy, upload, verify and activate a fresh `plan_id` with confirmation `INSTALL PORTAL` |
| `POST /api/portal/plan` | Inspect `server`, uploaded `directory` and selected `mode` (`pin` or `credentials`) |
| `POST /api/portal/install` | Activate a fresh `plan_id` with confirmation `INSTALL PORTAL` |

Voucher creation adds `credential_mode` (`pin` or `credentials`), `pin_length`, `username_prefix`, `username_length`, and `password_length`. Existing clients that omit these settings retain 10-digit PIN behavior. New voucher responses include username, password and credential_mode; `pin` is null for separate credentials.

## Validation limits

Automated tests cover escaped templates, credential generation, saved-template persistence, package contents, simulated activation/restore and stale-plan protection. Generated JavaScript is exercised with mock DOM/CHAP callbacks to verify PIN mapping, independent passwords, HTTPS behavior and HTTP-PAP refusal. This does not validate the router's MD5 library or actual captive-portal execution. Real browser rendering, printer layouts and RouterOS 7.24.2 installation/login still require acceptance testing.

Reference: [MikroTik Hotspot customization: servlet pages, CHAP and support files](https://help.mikrotik.com/docs/spaces/ROS/pages/87162881/Hotspot+customisation).

Transport and file operations: [RouterOS API](https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API), [RouterOS Files](https://help.mikrotik.com/docs/spaces/ROS/pages/2555971/Files).

## User profile selling prices

In **Vouchers & users → User profile prices**, select a profile, enter its price and currency (NGN by default), then save. For example, you can assign daily/three-day/weekly/monthly profiles NGN 500/1,000/2,000/5,000. These are selling prices only; configure the ticket duration separately.

Prices appear beside profiles and automatically flow into newly generated tickets, print previews and CSV exports. Tracked expiry batches retain the selected base profile's price even though the router uses a dedicated batch profile. Later price changes do not alter an existing batch. A saved price overrides the template fallback price; without a saved profile price, the template label is used. Zero prints as NGN 0.00; saving a blank amount removes the profile price.

Prices are local application metadata, scoped to router IP/identity and profile ID/name, stored under `data/prices`. They do not change RouterOS settings or collect payments. Back up this folder when moving the backend. A router IP/identity or profile change requires checking/re-entering prices. Owner phones using the same backend share these prices; separate installations do not synchronize them.
