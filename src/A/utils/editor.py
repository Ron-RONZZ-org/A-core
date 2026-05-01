"""Editor integration using $EDITOR."""

import os
import subprocess
import tempfile
from pathlib import Path


def edit_text(
    text: str = "",
    suffix: str = ".txt",
    language: str = None,
) -> str | None:
    """
    Open $EDITOR with text, return edited content.
    
    Args:
        text: Initial text
        suffix: File extension
        language: Language hint (optional)
        
    Returns:
        Edited text or None if cancelled
    """
    editor = os.environ.get("EDITOR", "vim")
    
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(text.encode())
        f.flush()
        path = f.name
    
    try:
        result = subprocess.run(
            [editor, path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None  # Cancelled
        
        with open(path) as f:
            return f.read()
    finally:
        Path(path).unlink(missing_ok=True)


def edit_file(path: Path) -> bool:
    """Open a file in $EDITOR."""
    editor = os.environ.get("EDITOR", "vim")
    result = subprocess.run([editor, str(path)])
    return result.returncode == 0