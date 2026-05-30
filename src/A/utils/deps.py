"""Dependency auto-install utilities.

Provides functions to ensure Python dependencies are available,
auto-installing them via ``uv pip`` / ``pip`` when missing.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from typing import Optional


def get_pip_command() -> list[str]:
    """Find the best available pip command, respecting venv isolation.

    Priority: ``uv`` > ``pip``/``pip3`` > ``python3 -m pip`` > ``sys.executable -m pip``

    Returns:
        pip command arguments ready for :func:`subprocess.check_call`.
    """
    uv_cmd = shutil.which("uv")
    if uv_cmd:
        return [uv_cmd, "pip"]

    pip_cmd = shutil.which("pip") or shutil.which("pip3")
    if pip_cmd:
        return [pip_cmd]

    python3 = shutil.which("python3")
    if python3:
        return [python3, "-m", "pip"]

    return [sys.executable, "-m", "pip"]


def ensure_dependency(
    module: str,
    package: Optional[str] = None,
    *,
    auto_install: bool = True,
    timeout: float = 120,
) -> None:
    """Ensure a Python dependency is available, auto-installing if needed.

    Tries via :func:`importlib.import_module`. On failure, prompts the user
    to install (if running in a TTY), then installs via :func:`get_pip_command`.

    Args:
        module: Import name (e.g. ``"openai"``, ``"httpx"``).
        package: pip package name (defaults to *module*).
        auto_install: If True (default), prompt user to install interactively.
                      If False, raise :exc:`ImportError` immediately.
        timeout: Maximum time in seconds for the install subprocess
                 (default 120). Passed to :func:`subprocess.run`.

    Raises:
        ImportError: If module not found and install was declined or failed.
    """
    if package is None:
        package = module

    # Fast path — already installed
    try:
        importlib.import_module(module)
        return
    except ImportError:
        if not auto_install or not sys.stdin.isatty():
            raise

    # Interactive install path (lazy imports to avoid circular deps)
    import typer
    from A import tr_multi
    from A.utils.output import info, error

    answer = typer.confirm(
        tr_multi(
            f"Bezonas '{package}' bibliotekon. Ĉu instali ĝin nun?",
            f"The '{package}' library is required. Install it now?",
            f"La bibliothèque '{package}' est nécessaire. Installer maintenant ?",
        ),
        default=True,
    )
    if not answer:
        raise ImportError(
            f"{package} library not installed. Install with: pip install {package}"
        )

    info(
        tr_multi(
            f"Instalado de '{package}'...",
            f"Installing '{package}'...",
            f"Installation de '{package}'...",
        )
    )

    try:
        pip_cmd = get_pip_command()
        completed = subprocess.run(
            pip_cmd + ["install", package],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(
                completed.returncode,
                completed.args,
                output=completed.stdout,
                stderr=completed.stderr,
            )
        importlib.invalidate_caches()
        importlib.import_module(module)
    except subprocess.TimeoutExpired:
        error(
            tr_multi(
                f"Instalado de '{package}' tempis (>{timeout}s).",
                f"Installation of '{package}' timed out (>{timeout}s).",
                f"L'installation de '{package}' a expiré (>{timeout}s).",
            )
        )
        raise ImportError(
            f"Failed to install {package}: timed out after {timeout}s"
        )
    except Exception as e:
        stderr_hint = ""
        if isinstance(e, subprocess.CalledProcessError) and e.stderr:
            stderr_hint = e.stderr.strip()[:500]
        detail = f": {stderr_hint}" if stderr_hint else ""
        error(
            tr_multi(
                f"Instalo de '{package}' malsukcesis{detail}",
                f"Installation of '{package}' failed{detail}",
                f"L'installation de '{package}' a échoué{detail}",
            )
        )
        raise ImportError(f"Failed to install {package}{detail}") from e


__all__ = ["get_pip_command", "ensure_dependency"]
