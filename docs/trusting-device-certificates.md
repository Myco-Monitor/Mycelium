# Trusting Your Myco-Monitor Certificates

The Myco-Monitor system uses **HTTPS everywhere**, secured by **two private
certificate authorities (CAs)**. Because they're private (not pre-installed in
your browser), you'll see warnings like *"Your connection is not private"* or
*"Warning: Potential Security Risk Ahead"* until you trust them. Import each one
**once per computer you browse from** to get a proper padlock.

| Certificate | File | Trusting it removes warnings on |
| --- | --- | --- |
| **Myco-Monitor CA** (devices) | [`config/ca_root.pem`](../config/ca_root.pem) | `https://spore-NNNN.local`, `https://hyphae-NNNN.local`, `https://192.168.4.1` (provisioning) |
| **Mycelium web-UI CA** (per install) | `config/mycelium_local_ca.pem` | `https://mycelium.local:8443` (the Mycelium app itself) |

Both are imported the **same way** — see [Install instructions](#install-instructions);
just repeat the steps for each file. The certificates already include the
hostnames above, so no further configuration is needed once a CA is trusted.

Two important differences between them:

- The **Myco-Monitor CA** ships with Mycelium and is the same for everyone — its
  fingerprint is fixed (below).
- The **Mycelium web-UI CA** is generated **locally** the first time you run
  `python run.py --https`, so it's **unique to your install**. It only exists if
  you serve Mycelium over HTTPS, and its fingerprint is printed at startup (verify
  with `openssl`, see [docs/deployment.md](deployment.md)).

> Note: this is about trusting pages **in your browser**. The Mycelium *app*
> already trusts your devices internally via the bundled
> [`config/ca_root.pem`](../config/ca_root.pem) — that part needs nothing from you.

---

## Get the certificate

The CA root certificate is **public** and ships with Mycelium at:

```
config/ca_root.pem
```

You can also download it straight from the repository
([config/ca_root.pem](../config/ca_root.pem) → "Raw" → Save As).

### Verify it before you install (recommended)

Installing a root CA is a position of trust, so confirm the file you downloaded
is the genuine Myco-Monitor CA before trusting it. The fingerprints must match:

| Field | Value |
| --- | --- |
| Subject | `CN = Myco-Monitor CA, O = Myco-Monitor` |
| Valid | 2026-02-22 → 2036-02-20 |
| SHA-256 | `41:4D:DF:39:BA:64:27:37:D8:40:D4:3F:90:0C:57:88:B1:FB:5D:4B:B9:4F:8E:61:FA:13:45:27:2F:2E:3D:F0` |
| SHA-1 | `23:BB:50:F0:5C:EF:F3:BE:8B:3E:A6:9E:D3:42:34:15:21:D8:6E:78` |

Check it yourself with OpenSSL:

```bash
openssl x509 -in ca_root.pem -noout -subject -dates -fingerprint -sha256
```

> **Trust scope:** trusting this root tells your browser to accept *any*
> certificate signed by the Myco-Monitor CA. That is what lets it vouch for your
> Spore and Hyphae devices. Only install it if you obtained it from an official
> Myco-Monitor source and the fingerprint matches above.

### The Mycelium web-UI CA (if you run Mycelium over HTTPS)

Grab this one from the machine running Mycelium:

```
config/mycelium_local_ca.pem
```

It's generated **locally on that machine** and is **unique to your install**, so
there's no published fingerprint. Confirm it matches what the server prints at
startup ("import this CA once: …"), or:

```bash
openssl x509 -in mycelium_local_ca.pem -noout -subject -fingerprint -sha256
# Subject must be: CN = Mycelium Local CA, O = Mycelium
```

---

## Install instructions

Pick your platform and **repeat the steps for each CA you're trusting**
(`ca_root.pem` for devices, `mycelium_local_ca.pem` for the Mycelium UI).
**Chrome, Edge, and Safari use the operating-system trust store**; **Firefox
keeps its own**, so Firefox users should also do the Firefox section.

### Windows (Chrome / Edge)

1. Rename the file to `myco-monitor-ca.crt` (so Windows recognizes it).
2. Double-click it → **Install Certificate**.
3. Choose **Current User** (or **Local Machine** for all users) → **Next**.
4. Select **Place all certificates in the following store** → **Browse** →
   **Trusted Root Certification Authorities** → **OK** → **Next** → **Finish**.
5. Accept the security prompt. Restart the browser.

Command-line alternative (admin PowerShell):

```powershell
certutil -addstore -f "Root" myco-monitor-ca.crt
```

### macOS (Safari / Chrome)

1. Double-click `ca_root.pem` to open **Keychain Access** (add to the **login**
   or **System** keychain).
2. Find **Myco-Monitor CA**, double-click it, expand **Trust**, and set
   **When using this certificate** to **Always Trust**.
3. Close the window and authenticate to save.

Command-line alternative:

```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain ca_root.pem
```

### Linux (system trust store)

**Debian / Ubuntu:**

```bash
sudo cp ca_root.pem /usr/local/share/ca-certificates/myco-monitor-ca.crt
sudo update-ca-certificates
```

**Fedora / RHEL / CentOS:**

```bash
sudo cp ca_root.pem /etc/pki/ca-trust/source/anchors/myco-monitor-ca.pem
sudo update-ca-trust
```

> On Linux, Chrome uses the NSS store and may not pick up the system CA. If so,
> use the **Firefox** steps below (Chrome shares the NSS database) or import via
> `certutil`.

### Firefox (all platforms)

Firefox has its own trust store, independent of the OS — so even if the CA is in
your OS store, you must also import it here.

1. **Settings → Privacy & Security → Connection and Software Security →
   Advanced Settings → Certificates → Manage Certificates…**
2. Open the **Authorities** tab → **Import…**
3. Select `ca_root.pem`.
4. Check **Trust this CA to identify websites** → **OK**, then **restart Firefox**.

### iOS / iPadOS (Safari)

1. Email or AirDrop `ca_root.pem` to the device, or download it in Safari, then
   open it. Tap **Allow** to download the configuration profile.
2. **Settings → General → VPN & Device Management** → tap the **Myco-Monitor CA**
   profile → **Install**.
3. Enable trust: **Settings → General → About → Certificate Trust Settings** →
   turn **ON** for **Myco-Monitor CA**.

### Android

Exact wording varies by version and manufacturer.

1. Copy `ca_root.pem` to the device.
2. **Settings → Security → Encryption & credentials → Install a certificate →
   CA certificate** (some phones: **Settings → Security → More → Install from
   storage**).
3. Select the file and confirm.

> Some Android versions warn that a third party may monitor traffic — this is the
> standard warning for any user-installed CA. Apps may still ignore user CAs;
> browsers will honor it for the device pages.

---

## Verify it worked

Open a page in your browser, for example:

```
https://192.168.4.1         (a device in setup/AP mode)        -> Myco-Monitor CA
https://spore-1234.local    (a configured Spore)               -> Myco-Monitor CA
https://mycelium.local:8443 (the Mycelium app, if on HTTPS)    -> Mycelium web-UI CA
```

You should now see a normal padlock and **no** certificate warning. If one URL
still warns, you likely haven't imported that URL's CA yet (the two are separate).

---

## Troubleshooting

- **Still warned after installing?** Fully quit and reopen the browser. Chrome
  and Edge sometimes need a restart to reload the OS trust store.
- **Firefox still warns but Chrome is fine (or vice-versa)?** They use separate
  stores — install into both.
- **Warning about the hostname / name mismatch?** Make sure you're visiting the
  device by its `*.local` mDNS name or `192.168.4.1`, not by a raw LAN IP — the
  certificate is issued for those names.
- **`*.local` won't resolve?** mDNS (Bonjour/Avahi) must be available on your
  network. On Linux install `avahi-daemon`; on Windows, Bonjour ships with
  several Apple products, otherwise use the device's IP.
- **Certificate expired?** The CA root is valid until 2036. If you see an expiry
  error before then, you likely installed an older or wrong certificate — remove
  it and re-install the current `config/ca_root.pem`.
