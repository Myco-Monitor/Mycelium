# Mycelium Deployment & Security

How Mycelium secures data, and what you (or an end user) need to do at deploy time.

## TL;DR

- **Browser ↔ Mycelium:** run with `--https` (or `"https": true` in config). A
  self-signed cert is auto-generated on first run; the UI is served on **8443**.
- **Secrets at rest:** the session key, SMTP password, and OWM API key are
  auto-generated/encrypted into the gitignored `data/` dir. **The user creates no
  secrets at setup** — it's automatic.
- **Mycelium ↔ devices:** already secured by `config/ca_root.pem` + device certs
  + PINs. Devices never connect to Mycelium, so they need **no** Mycelium cert.

---

## 1. HTTPS for the web UI

Mycelium serves plain HTTP on loopback by default (fine for same-machine use).
To encrypt logins/sessions over the network:

```bash
python run.py --https            # serves https://<host>:8443, self-signed cert
python run.py --https --host 0.0.0.0   # reachable across the LAN
```

On first `--https` run, a self-signed cert + key are generated into
`config/mycelium_cert.pem` / `config/mycelium_key.pem` (key `0600`, both
gitignored). The cert's SAN covers `mycelium.local`, the machine's real
`<hostname>.local`, `localhost`, `127.0.0.1`, and the detected LAN IP — so the
URL matches however you reach it.

### `mycelium.local`

When serving HTTPS on a non-loopback host, Mycelium advertises **`mycelium.local`**
over mDNS, so any computer on the LAN can browse to `https://mycelium.local:8443`
(consistent with `spore-NNNN.local` / `hyphae-NNNN.local`). Requires the client
OS to resolve `.local` (built in on macOS/Windows; install `avahi`/`nss-mdns` on
Linux).

### The browser warning (self-signed)

A self-signed cert encrypts traffic but isn't trusted by browsers, so you'll get
a one-time warning. Either accept it, or use a trusted cert (below).

### Bring your own cert (no warning)

Point Mycelium at any cert/key you provide — they take precedence over the
self-signed pair:

```bash
python run.py --cert /path/to/cert.pem --key /path/to/key.pem
# or drop them at config/mycelium_cert.pem + config/mycelium_key.pem
```

**Issuing a `mycelium.local` cert from the Myco-Monitor CA** (so browsers that
already trust `ca_root.pem` connect without warnings). On the air-gapped CA host:

```bash
# 1) key + CSR for the Mycelium host
openssl req -new -newkey rsa:2048 -nodes \
  -keyout mycelium_key.pem -out mycelium.csr \
  -subj "/CN=mycelium.local"

# 2) sign with the Myco-Monitor CA, with the SAN browsers will see
openssl x509 -req -in mycelium.csr -CA ca_root.pem -CAkey <ca_key> -CAcreateserial \
  -out mycelium_cert.pem -days 825 -sha256 \
  -extfile <(printf "subjectAltName=DNS:mycelium.local,IP:<lan-ip>")
```

Copy `mycelium_cert.pem` + `mycelium_key.pem` to the Mycelium host's `config/`.
Clients that trust `ca_root.pem` then get warning-free HTTPS.

> Note: this is for **your own / provisioned** deployments. The cert+key are
> per-host and must never be committed — open-source users get the self-signed
> path instead.

---

## 2. Secrets at rest (automatic)

All machine secrets live in the gitignored `data/` directory, owner-only (`0600`):

| Secret | File | Purpose |
|---|---|---|
| Session signing key | `data/.storage_secret` | signs login cookies (prevents forgery) |
| Encryption key | `data/.pin_key` | Fernet key for everything below |
| Device PINs | DB (`device_pins`) | encrypted with `.pin_key` |
| SMTP password | DB (`user_settings`) | encrypted with `.pin_key` |
| OWM API key | DB (`user_settings`) | encrypted with `.pin_key` |

These are generated on first use — **the user does nothing**. Encryption is
transparent: code reads/writes plaintext; ciphertext only exists on disk. Legacy
plaintext values (from before encryption) keep working and are encrypted on their
next save.

**Backups / migration:** keep `data/` together. If `data/.pin_key` is lost, the
encrypted SMTP/OWM/PIN values can't be decrypted (re-enter them); if
`data/.storage_secret` is lost, everyone is simply logged out (re-login).

---

## 3. Host hardening

Secret protection comes from the OS, not obscurity — so:

- **Run as a dedicated non-root user.** (HTTPS uses 8443, an unprivileged port,
  specifically so Mycelium never needs root.)
- **Keep `data/` permissions tight** (`0700`); Mycelium sets this on its secret
  files automatically.
- **For physical-theft threats** (e.g. a Pi in a grow room): use full-disk or
  `data/`-directory encryption. That protects *every* secret at once — far better
  than any per-file trick.

### Alternatives for remote / public access

- **Reverse proxy** (Caddy/nginx/Traefik) in front for a real Let's Encrypt cert
  if you have a public domain; Mycelium stays HTTP on loopback behind it.
- **Tailscale / WireGuard** for encrypted remote access without exposing the UI
  to the internet (Tailscale can also issue trusted certs for your tailnet).

---

## What is NOT required

- ❌ Provisioning any Mycelium certificate onto Spore/Hyphae devices — devices
  never talk to Mycelium, so they need no knowledge of it.
- ❌ The user manually creating any secret/key/password at setup time.
