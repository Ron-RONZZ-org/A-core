"""Import utilities for A-core - JSON/TOML import with auto-decryption."""

import json
from pathlib import Path
from typing import Generator, Any

from A.core.crypto import decrypt, is_encrypted as crypto_is_encrypted

# File magic for encrypted exports (shared with export.py)
ENCRYPTED_MAGIC = b"AES0"


def import_json(
    path: Path,
    decryption_password: str | None = None,
) -> list[dict]:
    """Import data from JSON format.

    Args:
        path: Path to JSON file
        decryption_password: Optional password for decryption

    Returns:
        List of records
    """
    data = path.read_bytes()

    # Check if encrypted
    if data.startswith(ENCRYPTED_MAGIC):
        if not decryption_password:
            raise ValueError("File is encrypted, password required")

        # Strip magic and decrypt
        decrypted = decrypt(data[4:], decryption_password)
        return json.loads(decrypted.decode("utf-8"))

    # Regular JSON
    return json.loads(data.decode("utf-8"))


def import_json_stream(
    path: Path,
    decryption_password: str | None = None,
) -> Generator[dict, None, None]:
    """Import JSON with streaming (memory efficient).

    Note: For encrypted files, must load all into memory first.

    Args:
        path: Path to JSON file
        decryption_password: Optional password

    Yields:
        Records one at a time
    """
    records = import_json(path, decryption_password)
    for record in records:
        yield record


def import_toml(
    path: Path,
    decryption_password: str | None = None,
) -> dict:
    """Import single record from TOML format.

    Args:
        path: Path to TOML file
        decryption_password: Optional password

    Returns:
        Single record as dict
    """
    import tomlkit

    data = path.read_bytes()

    # Check if encrypted
    if data.startswith(ENCRYPTED_MAGIC):
        if not decryption_password:
            raise ValueError("File is encrypted, password required")

        decrypted = decrypt(data[4:], decryption_password)
        return tomlkit.loads(decrypted.decode("utf-8")).unwrap()

    # Regular TOML
    return tomlkit.loads(data.decode("utf-8")).unwrap()


def import_toml_dir(
    dir_path: Path,
    decryption_password: str | None = None,
) -> Generator[dict, None, None]:
    """Import multiple TOML files from a directory.

    Args:
        dir_path: Directory containing TOML files
        decryption_password: Optional password

    Yields:
        Records from each TOML file
    """
    dir_path = Path(dir_path)

    for toml_file in sorted(dir_path.glob("*.toml")):
        # Skip encrypted marker files
        if toml_file.name.startswith("."):
            continue

        record = import_toml(toml_file, decryption_password)
        yield record


def import_auto(
    path: Path,
    decryption_password: str | None = None,
) -> list[dict] | dict:
    """Auto-detect format and import.

    Args:
        path: File to import
        decryption_password: Optional password

    Returns:
        List[dict] for JSON (multiple records)
        dict for TOML (single record)
    """
    data = path.read_bytes()

    # Check encrypted first
    if data.startswith(ENCRYPTED_MAGIC):
        if not decryption_password:
            raise ValueError("File is encrypted, password required")

        # Strip magic and decrypt
        decrypted = decrypt(data[4:], decryption_password)

        # Detect inner format
        if decrypted.startswith(b"["):
            return json.loads(decrypted.decode("utf-8"))
        else:
            import tomlkit
            return tomlkit.loads(decrypted.decode("utf-8")).unwrap()

    # Detect format from content
    data_str = data.decode("utf-8").strip()

    if data_str.startswith("["):
        return json.loads(data_str)
    elif "=" in data_str:
        import tomlkit
        return tomlkit.loads(data_str).unwrap()
    else:
        # Default to JSON
        return json.loads(data_str)


def import_stream(
    path: Path,
    decryption_password: str | None = None,
) -> Generator[dict, None, None]:
    """Auto-detect and stream import.

    For JSON files, streams records.
    For TOML directories, yields from each file.

    Args:
        path: File or directory to import
        decryption_password: Optional password

    Yields:
        Records one at a time
    """
    path = Path(path)

    if path.is_dir():
        # TOML directory
        yield from import_toml_dir(path, decryption_password)
    else:
        # Single file - detect format
        result = import_auto(path, decryption_password)

        if isinstance(result, list):
            for record in result:
                yield record
        else:
            yield result