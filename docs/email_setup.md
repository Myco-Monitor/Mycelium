# Email Notifications Setup (SMTP)

Mycelium sends email alerts for critical events (device offline, threshold
breach, relay failures) over SMTP. Configure it under **Settings → Email
Notifications**, then use **Send Test Email** to confirm it works.

## TL;DR (Gmail)

If you use a Gmail/Google Workspace account, your normal account password
**will not work** — Google blocks plain-password SMTP logins. You must:

1. Enable **2-Step Verification** on your Google account.
2. Generate a **16-character App Password**.
3. Paste that App Password into the **SMTP Password / App Password** field.

That's the single most common reason a test email fails.

---

## Settings fields

| Field | Value |
|---|---|
| **SMTP Server** | `smtp.gmail.com` (Gmail) |
| **SMTP Port** | `587` |
| **From Address** | your full Gmail address, e.g. `you@gmail.com` |
| **To Address** | where alerts are delivered (can be the same address) |
| **SMTP Password / App Password** | the **App Password**, *not* your login password |
| **Use STARTTLS** | **on** (required for port 587) |

The SMTP password is encrypted at rest with Fernet (see
[deployment.md](deployment.md) §2) — it is never stored in plaintext on disk.

---

## Generating a Gmail App Password

App Passwords require 2-Step Verification to be enabled first.

1. Enable 2-Step Verification: <https://myaccount.google.com/signinoptions/two-step-verification>
2. Open the App Passwords page: <https://myaccount.google.com/apppasswords>
3. Enter a name (e.g. `Mycelium`) and click **Create**.
4. Google shows a **16-character password** (four groups of four). Copy it.
5. Paste it into the **SMTP Password / App Password** field in Mycelium.
   You can paste it with or without the spaces.
6. Click **Save Email Settings**, then **Send Test Email**.

> The App Password is shown only once. If you lose it, just delete it on the
> App Passwords page and generate a new one.

---

## Other providers

Mycelium works with any SMTP provider. Use that provider's SMTP host, port, and
credentials. Many providers (Microsoft 365 / Outlook, Yahoo, etc.) also require
an app-specific password when 2FA is enabled.

| Provider | Server | Port | TLS |
|---|---|---|---|
| Gmail / Google Workspace | `smtp.gmail.com` | 587 | STARTTLS |
| Outlook / Microsoft 365 | `smtp.office365.com` | 587 | STARTTLS |
| Yahoo Mail | `smtp.mail.yahoo.com` | 587 | STARTTLS |
| Generic SSL (alternative) | provider's SSL host | 465 | implicit SSL |

For port **465**, providers use implicit SSL rather than STARTTLS; port **587**
with STARTTLS (the default here) is preferred where available.

---

## Troubleshooting

- **Test email fails with Gmail** → you're almost certainly using your account
  password instead of an App Password. Generate one (above).
- **`Username and Password not accepted`** → wrong password, or 2-Step
  Verification isn't enabled (so no App Password exists yet).
- **Connection times out** → wrong server/port, or STARTTLS is off on port 587.
- **Email sends but never arrives** → check your **spam/junk** folder and mark
  the message *Not Spam*; alerts often land there until the sender is trusted.
