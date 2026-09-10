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

1. In Template editor choose the desired layout and branding, then select **Download portal installation ZIP**.
2. Extract the ZIP on your computer and read `INSTALL.txt`. The package contains branded `login.html`, `flogin.html` and `portal.css`, plus template JSON and instructions. It is an **overlay**, not a full replacement for RouterOS's default hotspot files.
3. Use WinBox to download a backup of the router's entire currently selected hotspot directory.
4. Copy that directory on your computer into a **new** folder such as `nelsonict-pin` or `nelsonict-credentials`. Overlay the three generated files. Preserve the original `md5.js`, `alogin.html`, `status.html`, `logout.html`, `redirect.html` and other support files.
5. Upload the completed new folder through **WinBox → Files**. On devices using persistent flash storage, use an appropriate folder such as `flash/nelsonict-pin`. Do not overwrite/delete the old portal folder. RouterOS file uploads are a manual WinBox step in this release.
6. Connect the app to the router. Select the hotspot server and actual uploaded directory, then **Check installation**. Review the affected server profile, previous directory, authentication method and all servers sharing that profile.
7. The check confirms required filenames exist. It does **not** establish that their contents match the downloaded package. Verify that you uploaded the intended files. Existing nonempty HTML-directory overrides are rejected for manual review.
8. Enter `INSTALL PORTAL` to activate. This changes only the server profile's `html-directory`; it does not change authentication methods, passwords, bandwidth or expiry policies.
9. Test from a client that is not already logged in. PIN mode requires username=password. Existing users with independent passwords need the two-field portal; switching a shared profile to PIN-only can prevent those users from logging in.
10. To revert, open **Change history** and use Rollback additions on the portal-install record. For this record type it restores the previous HTML directory. It refuses if the profile was subsequently changed or has an override. You can also restore HTML Directory directly in WinBox. Keep the old files available.

The portal supports RouterOS **HTTP-CHAP** using the router's existing `md5.js` or **HTTPS** authentication. It refuses unencrypted HTTP-PAP fallback. HTTPS submissions remain on HTTPS. The installer requires a pre-existing compatible authentication method and does not provision captive-portal certificates. Login errors use a generic message rather than reflecting arbitrary submitted credentials.

Use a distinct new directory for later portal updates so directory rollback remains meaningful. The demo contains simulated uploaded folders; those files do not exist on a real router until you upload them.

## API additions

All routes use the existing owner token and Origin checks:

| Endpoint | Purpose |
|---|---|
| `POST /api/templates/list` | List built-in and locally saved templates |
| `POST /api/templates/save` | Validate/save `template`; saving id `default` creates a new ID |
| `POST /api/templates/render` | Return script-free printable HTML for `template`, optionally `vouchers`; without vouchers uses marked samples |
| `POST /api/templates/export` | Return a base64 ZIP and filename for the portal overlay |
| `POST /api/portal/plan` | Inspect `server`, uploaded `directory` and selected `mode` (`pin` or `credentials`) |
| `POST /api/portal/install` | Activate a fresh `plan_id` with confirmation `INSTALL PORTAL` |

Voucher creation adds `credential_mode` (`pin` or `credentials`), `pin_length`, `username_prefix`, `username_length`, and `password_length`. Existing clients that omit these settings retain 10-digit PIN behavior. New voucher responses include username, password and credential_mode; `pin` is null for separate credentials.

## Validation limits

Automated tests cover escaped templates, credential generation, saved-template persistence, package contents, simulated activation/restore and stale-plan protection. Generated JavaScript is exercised with mock DOM/CHAP callbacks to verify PIN mapping, independent passwords, HTTPS behavior and HTTP-PAP refusal. This does not validate the router's MD5 library or actual captive-portal execution. Real browser rendering, printer layouts and RouterOS 7.24.2 installation/login still require acceptance testing.

Reference: [MikroTik Hotspot customization: servlet pages, CHAP and support files](https://help.mikrotik.com/docs/spaces/ROS/pages/87162881/Hotspot+customisation).
