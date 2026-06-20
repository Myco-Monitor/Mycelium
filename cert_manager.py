"""Self-signed TLS certificate management for the Mycelium web server.

Generates (once) a self-signed cert + key so the UI can be served over HTTPS,
with a SAN covering every way a user might reach the box: ``mycelium.local``,
the host's real ``<hostname>.local``, ``localhost``, ``127.0.0.1``, and the
primary LAN IP. Files are written into ``config/`` (gitignored), key at 0600.

Bring-your-own: point the ssl paths at any cert/key you provide instead -- e.g.
one issued by the Myco-Monitor CA for ``mycelium.local`` so browsers trusting
``ca_root.pem`` connect without a warning. See docs/deployment.md.
"""

import datetime
import ipaddress
import os
import socket
from pathlib import Path
from typing import Optional, Tuple

_CONFIG_DIR = Path(__file__).parent / "config"
DEFAULT_CERT = _CONFIG_DIR / "mycelium_cert.pem"
DEFAULT_KEY = _CONFIG_DIR / "mycelium_key.pem"
MDNS_HOSTNAME = "mycelium.local"


def primary_lan_ip() -> Optional[str]:
    """Best-effort primary LAN IPv4 (the default-route interface). None if offline."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # No packets are actually sent; this just selects the default iface.
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def _san():
    from cryptography import x509

    dns_names = ["mycelium.local", "localhost"]
    host = socket.gethostname()
    if host:
        if host not in dns_names:
            dns_names.append(host)
        fqdn = host if host.endswith(".local") else f"{host}.local"
        if fqdn not in dns_names:
            dns_names.append(fqdn)

    entries = [x509.DNSName(n) for n in dict.fromkeys(dns_names)]
    entries.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
    lan = primary_lan_ip()
    if lan and lan != "127.0.0.1":
        entries.append(x509.IPAddress(ipaddress.ip_address(lan)))
    return entries


def ensure_cert(
    cert_path: Optional[str] = None, key_path: Optional[str] = None
) -> Tuple[str, str]:
    """Return ``(cert_path, key_path)``, generating a self-signed pair if absent.

    If both files already exist (self-signed from a prior run, or a cert you
    supplied), they are used unchanged.
    """
    cert_p = Path(cert_path) if cert_path else DEFAULT_CERT
    key_p = Path(key_path) if key_path else DEFAULT_KEY

    if cert_p.exists() and key_p.exists():
        return str(cert_p), str(key_p)

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mycelium.local")])
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))  # 10y; local self-signed
        .add_extension(x509.SubjectAlternativeName(_san()), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    cert_p.parent.mkdir(parents=True, exist_ok=True)
    key_bytes = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    # Private key: owner-only. Cert: world-readable is fine (it's public).
    fd = os.open(str(key_p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key_bytes)
    finally:
        os.close(fd)
    cert_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(cert_p), str(key_p)
