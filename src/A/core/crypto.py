"""Cryptography utilities for A-core - AES-256-GCM encryption."""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import os
import base64


# AES-256-GCM nonce size (12 bytes recommended by NIST)
NONCE_SIZE = 12
# Key size (256 bits = 32 bytes)
KEY_SIZE = 32
# Recommended PBKDF2 iterations (as of 2024)
PBKDF2_ITERATIONS = 600_000


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password using PBKDF2-HMAC-SHA256.

    Args:
        password: User password (str)
        salt: Random salt (16 bytes)

    Returns:
        Derived key (32 bytes)
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend(),
    )
    return kdf.derive(password.encode())


def generate_salt() -> bytes:
    """Generate a random 16-byte salt.

    Returns:
        Random salt (16 bytes)
    """
    return os.urandom(16)


def generate_nonce() -> bytes:
    """Generate a random 12-byte nonce for AES-GCM.

    Returns:
        Random nonce (12 bytes)
    """
    return os.urandom(NONCE_SIZE)


def encrypt(plaintext: bytes, password: str, salt: bytes | None = None) -> bytes:
    """Encrypt data with AES-256-GCM.

    Args:
        plainbytes: Data to encrypt
        password: User password
        salt: Optional salt (16 bytes). If None, generates random.

    Returns:
        Encrypted data: salt (16) + nonce (12) + ciphertext + tag (16)
    """
    if salt is None:
        salt = generate_salt()

    key = derive_key(password, salt)
    nonce = generate_nonce()
    aesgcm = AESGCM(key)

    # Encrypt and tag (authentication tag appended automatically)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Format: salt (16) + nonce (12) + ciphertext + tag (16)
    return salt + nonce + ciphertext


def decrypt(encrypted_data: bytes, password: str) -> bytes:
    """Decrypt AES-256-GCM encrypted data.

    Args:
        encrypted_data: Data encrypted with encrypt()
        password: User password (must match encryption password)

    Returns:
        Original plaintext

    Raises:
        cryptography.exceptions.InvalidTag: Wrong password or corrupted data
    """
    # Parse: salt (16) + nonce (12) + ciphertext + tag (16)
    salt = encrypted_data[:16]
    nonce = encrypted_data[16:28]
    ciphertext = encrypted_data[28:]

    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    return aesgcm.decrypt(nonce, ciphertext, None)


def encrypt_str(plaintext: str, password: str, salt: bytes | None = None) -> bytes:
    """Encrypt a string (convenience wrapper).

    Args:
        plaintext: String to encrypt
        password: User password
        salt: Optional salt

    Returns:
        Encrypted data as bytes
    """
    return encrypt(plaintext.encode("utf-8"), password, salt)


def decrypt_str(encrypted_data: bytes, password: str) -> str:
    """Decrypt to string (convenience wrapper).

    Args:
        encrypted_data: Encrypted bytes
        password: User password

    Returns:
        Original string
    """
    return decrypt(encrypted_data, password).decode("utf-8")


def is_encrypted(data: bytes) -> bool:
    """Check if data appears to be encrypted (minimum size check).

    Args:
        data: Data to check

    Returns:
        True if data length suggests encryption
    """
    # Minimum: salt (16) + nonce (12) + tag (16) = 44 bytes
    return len(data) >= 44


def encrypt_file(input_path: str, output_path: str, password: str) -> None:
    """Encrypt a file.

    Args:
        input_path: Path to plaintext file
        output_path: Path to write encrypted file
        password: User password
    """
    with open(input_path, "rb") as f:
        plaintext = f.read()

    encrypted = encrypt(plaintext, password)

    with open(output_path, "wb") as f:
        f.write(encrypted)


def decrypt_file(input_path: str, output_path: str, password: str) -> None:
    """Decrypt a file.

    Args:
        input_path: Path to encrypted file
        output_path: Path to write decrypted file
        password: User password
    """
    with open(input_path, "rb") as f:
        encrypted = f.read()

    plaintext = decrypt(encrypted, password)

    with open(output_path, "wb") as f:
        f.write(plaintext)