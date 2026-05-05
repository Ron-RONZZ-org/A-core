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
) -> None:
    """Ensure a Python dependency is available, auto-installing if needed.

    Tries via :func:`importlib.import_module`. On failure, prompts the user
    to install (if running in a TTY), then installs via :func:`get_pip_command`.

    Args:
        module: Import name (e.g. ``"openai"``, ``"httpx"``).
        package: pip package name (defaults to *module*).
        auto_install: If True (default), prompt user to install interactively.
                      If False, raise :exc:`ImportError` immediately.

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
        subprocess.check_call(
            pip_cmd + ["install", package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        importlib.invalidate_caches()
        importlib.import_module(module)
    except Exception as e:
        error(
            tr_multi(
                f"Instalo de '{package}' malsukcesis: {e}",
                f"Installation of '{package}' failed: {e}",
                f"L'installation de '{package}' a échoué : {e}",
            )
        )
        raise ImportError(f"Failed to install {package}: {e}") from e


__all__ = ["get_pip_command", "ensure_dependency"]
