"""Tests for A-core import module."""

import pytest
from pathlib import Path
import tempfile
import json


def test_import_json():
    """Test JSON import."""
    from A.core.export import export_json
    from A.core.import_ import import_json

    data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    with tempfile.TemporaryDirectory() as tmpdir:
        export_path = Path(tmpdir) / "export.json"
        export_json(data, export_path)

        imported = import_json(export_path)
        assert imported == data


def test_import_json_encrypted():
    """Test encrypted JSON import."""
    from A.core.export import export_json
    from A.core.import_ import import_json

    data = [{"id": 1, "name": "Secret"}]
    password = "export-password"

    with tempfile.TemporaryDirectory() as tmpdir:
        enc_path = Path(tmpdir) / "export.enc"
        export_json(data, enc_path, encryption_password=password)

        imported = import_json(enc_path, decryption_password=password)
        assert imported == data


def test_import_json_encrypted_wrong_password():
    """Test encrypted import with wrong password."""
    from A.core.export import export_json
    from A.core.import_ import import_json
    from cryptography.exceptions import InvalidTag

    data = [{"id": 1}]
    password = "correct-password"

    with tempfile.TemporaryDirectory() as tmpdir:
        enc_path = Path(tmpdir) / "export.enc"
        export_json(data, enc_path, encryption_password=password)

        with pytest.raises(InvalidTag):
            import_json(enc_path, decryption_password="wrong-password")


def test_import_json_encrypted_no_password():
    """Test encrypted import without password."""
    from A.core.export import export_json
    from A.core.import_ import import_json

    data = [{"id": 1}]

    with tempfile.TemporaryDirectory() as tmpdir:
        enc_path = Path(tmpdir) / "export.enc"
        export_json(data, enc_path, encryption_password="test")

        with pytest.raises(ValueError, match="password required"):
            import_json(enc_path)


def test_import_toml():
    """Test TOML import."""
    from A.core.export import export_toml
    from A.core.import_ import import_toml

    data = {"id": 1, "name": "Alice", "active": True}

    with tempfile.TemporaryDirectory() as tmpdir:
        toml_path = Path(tmpdir) / "record.toml"
        export_toml(data, toml_path)

        imported = import_toml(toml_path)
        assert imported["id"] == 1
        assert imported["name"] == "Alice"


def test_import_auto_json():
    """Test auto-import JSON."""
    from A.core.export import export_json
    from A.core.import_ import import_auto

    data = [{"id": 1}, {"id": 2}]

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "data.json"
        export_json(data, json_path)

        imported = import_auto(json_path)
        assert imported == data


def test_import_auto_toml():
    """Test auto-import TOML."""
    from A.core.export import export_toml
    from A.core.import_ import import_auto

    data = {"id": 1, "name": "Test"}

    with tempfile.TemporaryDirectory() as tmpdir:
        toml_path = Path(tmpdir) / "data.toml"
        export_toml(data, toml_path)

        imported = import_auto(toml_path)
        assert imported["id"] == 1


def test_import_auto_encrypted():
    """Test auto-import encrypted file."""
    from A.core.export import export_json
    from A.core.import_ import import_auto

    data = [{"id": 1, "secret": "data"}]
    password = "auto-password"

    with tempfile.TemporaryDirectory() as tmpdir:
        enc_path = Path(tmpdir) / "data.enc"
        export_json(data, enc_path, encryption_password=password)

        imported = import_auto(enc_path, decryption_password=password)
        assert imported == data


def test_import_stream_json():
    """Test streaming import from JSON."""
    from A.core.export import export_json
    from A.core.import_ import import_stream

    data = [{"id": i} for i in range(50)]

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "data.json"
        export_json(data, json_path)

        imported = list(import_stream(json_path))
        assert len(imported) == 50
        assert imported[0]["id"] == 0