import os
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pathlib import Path
import ipaddress

def generate_self_signed_cert(cert_path: Path, key_path: Path, ip_address: str = "127.0.0.1"):
    # Ensure directory exists
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Write key
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    
    # Generate certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"auralink"),
    ])
    
    san_list = [
        x509.DNSName(u"localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    
    try:
        san_list.append(x509.IPAddress(ipaddress.ip_address(ip_address)))
    except ValueError:
        san_list.append(x509.DNSName(ip_address))

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # 10 years
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName(san_list),
        critical=False,
    ).sign(key, hashes.SHA256())
    
    # Write certificate
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

if __name__ == "__main__":
    from config import CONFIG, BASE_DIR
    host = CONFIG.get("server", {}).get("host", "127.0.0.1")
    cert_file = BASE_DIR / CONFIG.get("server", {}).get("cert", "certs/cert.pem")
    key_file = BASE_DIR / CONFIG.get("server", {}).get("key", "certs/key.pem")
    
    print(f"Generando certificados para {host}...")
    generate_self_signed_cert(cert_file, key_file, host)
    print(f"Certificados generados en {cert_file.parent}")
