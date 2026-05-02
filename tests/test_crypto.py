"""Tests for A-core crypto module."""

import pytest
from pathlib import Path
import tempfile
import os


def test_encrypt_decrypt_roundtrip():
    """Test encryption/decryption produces original data."""
    from A.core.crypto import encrypt, decrypt, generate_salt

    plaintext = b"Hello, world!"
    password = "test-password-123"

    encrypted = encrypt(plaintext, password)
    decrypted = decrypt(encrypted, password)

    assert decrypted == plaintext


def test_encrypt_str_roundtrip():
    """Test string encryption convenience functions."""
    from A.core.crypto import encrypt_str, decrypt_str

    plaintext = "Saluton, mondo!"
    password = "test-password-123"

    encrypted = encrypt_str(plaintext, password)
    decrypted = decrypt_str(encrypted, password)

    assert decrypted == plaintext


def test_different_salts_produce_different_output():
    """Same plaintext with different salts produces different ciphertext."""
    from A.core.crypto import encrypt

    plaintext = b"Hello"
    password = "password"

    encrypted1 = encrypt(plaintext, password)
    encrypted2 = encrypt(plaintext, password)

    # Should be different due to random salt/nonce
    assert encrypted1 != encrypted2


def test_wrong_password_fails():
    """Decryption with wrong password raises exception."""
    from A.core.crypto import encrypt, decrypt
    from cryptography.exceptions import InvalidTag

    plaintext = b"Secret data"
    password = "correct-password"
    wrong_password = "wrong-password"

    encrypted = encrypt(plaintext, password)

    with pytest.raises(InvalidTag):
        decrypt(encrypted, wrong_password)


def test_is_encrypted():
    """Test encrypted data detection."""
    from A.core.crypto import encrypt, is_encrypted

    plaintext = b"Data"
    password = "password"

    encrypted = encrypt(plaintext, password)

    assert is_encrypted(encrypted)
    assert not is_encrypted(plaintext)


def test_encrypt_file():
    """Test file encryption."""
    from A.core.crypto import encrypt_file, decrypt_file

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.txt"
        encrypted_path = Path(tmpdir) / "encrypted.bin"
        decrypted_path = Path(tmpdir) / "decrypted.txt"

        # Write test file
        original_content = "Test content for encryption"
        input_path.write_text(original_content)

        password = "file-password"

        # Encrypt
        encrypt_file(str(input_path), str(encrypted_path), password)
        assert encrypted_path.exists()

        # Decrypt
        decrypt_file(str(encrypted_path), str(decrypted_path), password)
        assert decrypted_path.read_text() == original_content


def test_derive_key_consistency():
    """Same password + salt produces same key."""
    from A.core.crypto import derive_key

    password = "my-password"
    salt = b"1234567890123456"  # 16 bytes

    key1 = derive_key(password, salt)
    key2 = derive_key(password, salt)

    assert key1 == key2


def test_generate_salt():
    """Test salt generation."""
    from A.core.crypto import generate_salt, generate_nonce

    salt = generate_salt()
    nonce = generate_nonce()

    assert len(salt) == 16
    assert len(nonce) == 12