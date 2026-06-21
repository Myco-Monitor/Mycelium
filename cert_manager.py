"""TLS certificate management for the Mycelium web server.

Uses a per-install **local CA** model (like mkcert): on first ``--https`` run
Mycelium generates a small local CA, then issues the web-server (leaf) cert from
it. The user imports the local CA cert **once** into their browser/OS trust
store -- the same way ``ca_root.pem`` is trusted -- and then gets warning-free
HTTPS that survives leaf-cert regeneration.

This keeps each deployment self-contained: nobody has to get their cert signed
by the Myco-Monitor production CA. (That CA is for the *devices*.)

Files (all in ``config/``, gitignored; keys 0600):
  - ``mycelium_local_ca.pem``      -- import THIS into your browser
  - ``mycelium_local_ca_key.pem``  -- the local CA private key
  - ``mycelium_cert.pem`` / ``mycelium_key.pem`` -- the served leaf cert + key

Bring-your-own: point the ssl paths at any cert/key instead (e.g. one issued by
the Myco-Monitor CA for ``mycelium.local``) and the local CA is not used. See
docs/deployment.md.
"""

import datetime
import ipaddress
import os
import socket
from pathlib import Path
from typing import List, Optional, Tuple

_CONFIG_DIR = Path(__file__).parent / "config"
DEFAULT_CERT = _CONFIG_DIR / "mycelium_cert.pem"
DEFAULT_KEY = _CONFIG_DIR / "mycelium_key.pem"
LOCAL_CA_CERT = _CONFIG_DIR / "mycelium_local_ca.pem"
LOCAL_CA_KEY = _CONFIG_DIR / "mycelium_local_ca_key.pem"
MDNS_HOSTNAME = "mycelium.local"

_VALIDITY_DAYS = 3650  # 10y; local self-managed PKI, avoid renewal churn


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


def _write_private(path: Path, data: bytes) -> None:
    """Write owner-only (0600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _san() -> List:
    from cryptography import x509

    dns_names = ["mycelium.local", "localhost"]
    host = socket.gethostname()
    if host:
        if host not in dns_names:
            dns_names.append(host)
        fqdn = host if host.endswith(".local") else f"{host}.local"
        if fqdn not in dns_names:
            dns_names.append(fqdn)

    entries: List = [x509.DNSName(n) for n in dict.fromkeys(dns_names)]
    entries.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
    lan = primary_lan_ip()
    if lan and lan != "127.0.0.1":
        entries.append(x509.IPAddress(ipaddress.ip_address(lan)))
    return entries


def _load_or_create_local_ca():
    """Return (ca_cert, ca_key) cryptography objects, persisting on first use."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    if LOCAL_CA_CERT.exists() and LOCAL_CA_KEY.exists():
        ca_cert = x509.load_pem_x509_certificate(LOCAL_CA_CERT.read_bytes())
        ca_key = serialization.load_pem_private_key(
            LOCAL_CA_KEY.read_bytes(), password=None
        )
        return ca_cert, ca_key

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Mycelium Local CA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Mycelium"),
        ]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=_VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_CA_CERT.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    _write_private(
        LOCAL_CA_KEY,
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    return ca_cert, ca_key


def ensure_cert(
    cert_path: Optional[str] = None, key_path: Optional[str] = None
) -> Tuple[str, str]:
    """Return ``(cert_path, key_path)``, generating a CA-issued leaf if absent.

    If both files already exist (a prior run's leaf, or a cert you supplied),
    they are used unchanged.
    """
    cert_p = Path(cert_path) if cert_path else DEFAULT_CERT
    key_p = Path(key_path) if key_path else DEFAULT_KEY

    if cert_p.exists() and key_p.exists():
        return str(cert_p), str(key_p)

    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    ca_cert, ca_key = _load_or_create_local_ca()

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.datetime.now(datetime.timezone.utc)
    leaf = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mycelium.local")])
        )
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=_VALIDITY_DAYS))
        .add_extension(x509.SubjectAlternativeName(_san()), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    cert_p.parent.mkdir(parents=True, exist_ok=True)
    _write_private(
        key_p,
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    cert_p.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    return str(cert_p), str(key_p)


def local_ca_path() -> Optional[str]:
    """Path to the local CA cert to import into a trust store, or None if unused."""
    return str(LOCAL_CA_CERT) if LOCAL_CA_CERT.exists() else None
