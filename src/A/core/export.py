"""Export utilities for A-core - JSON/TOML export with optional AES encryption."""

import json
import tomllib
from pathlib import Path
from typing import Generator, Any

from A.core.crypto import encrypt, is_encrypted


# File magic for encrypted exports
ENCRYPTED_MAGIC = b"AES0"


def export_json(
    data: list[dict],
    output_path: Path,
    encryption_password: str | None = None,
) -> None:
    """Export data to JSON format.

    Args:
        data: List of records to export
        output_path: Path to write JSON file
        encryption_password: Optional password for encryption
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    if encryption_password:
        # Add magic bytes and encrypt
        encrypted = ENCRYPTED_MAGIC + encrypt(json_str.encode("utf-8"), encryption_password)
        output_path.write_bytes(encrypted)
    else:
        output_path.write_text(json_str, "utf-8")


def export_json_stream(
    generator: Generator[dict, None, None],
    output_path: Path,
    encryption_password: str | None = None,
) -> None:
    """Export data to JSON format using streaming (generator).

    For large datasets to avoid memory issues.

    Args:
        generator: Yields records one at a time
        output_path: Path to write JSON file
        encryption_password: Optional password for encryption
    """
    if encryption_password:
        # For encryption, we need to buffer (can't stream encrypt easily)
        # TODO: Consider chunked encryption for large files
        data = list(generator)
        export_json(data, output_path, encryption_password)
        return

    # Stream write for unencrypted
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[\n")
        first = True
        for record in generator:
            if not first:
                f.write(",\n")
            f.write(json.dumps(record, ensure_ascii=False))
            first = False
        f.write("\n]")


def export_toml(
    data: dict,
    output_path: Path,
    encryption_password: str | None = None,
) -> None:
    """Export single record to TOML format.

    Args:
        data: Single record to export
        output_path: Path to write TOML file
        encryption_password: Optional password for encryption
    """
    import tomlkit

    toml_str = tomlkit.dumps(data)

    if encryption_password:
        encrypted = ENCRYPTED_MAGIC + encrypt(toml_str.encode("utf-8"), encryption_password)
        output_path.write_bytes(encrypted)
    else:
        output_path.write_text(toml_str, "utf-8")


def export_toml_stream(
    generator: Generator[dict, None, None],
    output_path: Path,
    encryption_password: str | None = None,
) -> None:
    """Export multiple records to separate TOML files (one per record).

    Args:
        generator: Yields records one at a time
        output_path: Directory to write TOML files (one per record)
        encryption_password: Optional password for encryption
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    for i, record in enumerate(generator):
        # Create filename from record (use uuid if available)
        filename = record.get("uuid", f"record-{i:04d}") + ".toml"
        record_path = output_path / filename
        export_toml(record, record_path, encryption_password)


def is_encrypted_file(path: Path) -> bool:
    """Check if a file is encrypted.

    Args:
        path: Path to check

    Returns:
        True if file appears to be encrypted
    """
    data = path.read_bytes()
    return data.startswith(ENCRYPTED_MAGIC)


def detect_format(path: Path) -> str:
    """Detect file format (json/toml/encrypted).

    Args:
        path: File to check

    Returns:
        Format: "json", "toml", or "encrypted"
    """
    data = path.read_bytes()

    if data.startswith(ENCRYPTED_MAGIC):
        return "encrypted"

    # Check for JSON indicators
    data_stripped = data.lstrip()
    if data_stripped.startswith(b"{"):
        return "json"
    if data_stripped.startswith(b"["):
        return "json"

    # Check for TOML indicators (key = value patterns)
    # TOML typically has multiple lines with = signs
    text = data.decode("utf-8", errors="ignore")
    if "=" in text and text.count("\n") > 1:
        return "toml"

    # Default to JSON
    return "json"