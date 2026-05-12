"""Subprocess utilities."""

import subprocess
import shutil
from dataclasses import dataclass


@dataclass
class SubprocessResult:
    """Result from a subprocess call."""
    returncode: int
    stdout: str = ""
    stderr: str = ""
    
    @property
    def success(self) -> bool:
        return self.returncode == 0


def run(
    *args: str,
    timeout: float = 30.0,
    input: str = None,
) -> SubprocessResult:
    """
    Run a command safely with timeout.
    
    Args:
        *args: Command and arguments
        timeout: Max seconds to wait
        input: Optional stdin input
        
    Returns:
        SubprocessResult with returncode, stdout, stderr
    """
    try:
        result = subprocess.run(
            list(args),
            capture_output=True,
            timeout=timeout,
            input=input if input else None,
            text=True,
        )
        return SubprocessResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired:
        return SubprocessResult(returncode=124, stderr="timeout")
    except FileNotFoundError:
        return SubprocessResult(returncode=127, stderr=f"command not found: {args[0]}")


def has_command(name: str) -> bool:
    """Check if a command is available."""
    return shutil.which(name) is not None