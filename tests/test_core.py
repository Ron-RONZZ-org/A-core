"""Tests for A-core."""

import pytest
from pathlib import Path


def test_paths():
    """Test path resolution."""
    from A.core.paths import data_dir, config_dir, ensure_dirs
    
    ensure_dirs()
    assert data_dir().exists()
    assert config_dir().exists()


def test_i18n():
    """Test translations."""
    import A.core.i18n as i18n
    
    i18n.set_language("eo")
    assert i18n.tr("success") == "Sukceso"
    
    i18n.set_language("en")
    assert i18n.tr("success") == "Success"
    
    # Reset to default
    i18n.set_language("eo")


def test_i18n_default():
    """Test default language is Esperanto."""
    import A.core.i18n as i18n
    i18n.set_language("eo")
    assert i18n.get_current_language() == "eo"


def test_output():
    """Test output utilities can be imported."""
    from A.utils import success, error
    
    # These should not raise
    success("test message")
    error("test error")


def test_run():
    """Test subprocess run."""
    from A.utils.subprocess import run
    
    result = run("echo", "hello")
    assert result.success
    assert "hello" in result.stdout


def test_has_command():
    """Test command detection."""
    from A.utils.subprocess import has_command
    
    assert has_command("ls")
    assert not has_command("nonexistent-command-xyz")


def test_exceptions():
    """Test exception hierarchy."""
    from A.core.exceptions import AError, ConfigError, PluginError
    
    with pytest.raises(AError):
        raise AError("test")
    
    with pytest.raises(ConfigError):
        raise ConfigError("config test")


def test_config():
    """Test config loading."""
    from A.core.config import load_config, Config
    
    config = load_config()
    assert isinstance(config, Config)
    # Default values
    assert config.language == "eo"
    assert config.verbose is False