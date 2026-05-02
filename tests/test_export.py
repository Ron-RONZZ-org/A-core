"""Tests for A-core export/import modules."""

import pytest
from pathlib import Path
import tempfile
import json


def test_export_json():
    """Test JSON export."""
    from A.core.export import export_json

    data = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "export.json"

        export_json(data, output_path)

        loaded = json.loads(output_path.read_text("utf-8"))
        assert loaded == data


def test_export_json_encrypted():
    """Test encrypted JSON export."""
    from A.core.export import export_json, is_encrypted_file

    data = [{"id": 1, "name": "Secret"}]
    password = "export-password"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "export.enc"

        export_json(data, output_path, encryption_password=password)

        # Check it's encrypted
        assert is_encrypted_file(output_path)


def test_export_toml():
    """Test TOML export."""
    from A.core.export import export_toml

    data = {"id": 1, "name": "Alice", "active": True}

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "record.toml"

        export_toml(data, output_path)

        content = output_path.read_text("utf-8")
        assert "id = 1" in content
        assert "name = \"Alice\"" in content


def test_export_json_stream():
    """Test streaming JSON export."""
    import json
    from A.core.export import export_json_stream

    def record_generator():
        for i in range(100):
            yield {"id": i, "value": f"item-{i}"}

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "stream.json"

        export_json_stream(record_generator(), output_path)

        loaded = json.loads(output_path.read_text("utf-8"))
        assert len(loaded) == 100
        assert loaded[0]["id"] == 0
        assert loaded[99]["id"] == 99


def test_is_encrypted_file():
    """Test encrypted file detection."""
    from A.core.export import is_encrypted_file, export_json

    data = [{"id": 1}]
    password = "test-password"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Plain file
        plain_path = Path(tmpdir) / "plain.json"
        export_json(data, plain_path)
        assert not is_encrypted_file(plain_path)

        # Encrypted file
        enc_path = Path(tmpdir) / "enc.json"
        export_json(data, enc_path, encryption_password=password)
        assert is_encrypted_file(enc_path)


def test_detect_format():
    """Test format detection."""
    from A.core.export import export_json, detect_format

    data = [{"id": 1}]

    with tempfile.TemporaryDirectory() as tmpdir:
        # JSON
        json_path = Path(tmpdir) / "data.json"
        export_json(data, json_path)
        assert detect_format(json_path) == "json"

        # Encrypted
        enc_path = Path(tmpdir) / "data.enc"
        export_json(data, enc_path, encryption_password="pass")
        assert detect_format(enc_path) == "encrypted"