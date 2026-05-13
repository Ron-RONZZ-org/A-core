"""Uzanto — user profile management CLI for A-core.

Provides commands to view and modify the user's A-core configuration
(language, settings) as stored in ``~/.config/A/config.toml``.

Usage:
    A uzanto          — show help
    A uzanto vidi     — view current profile
    A uzanto modifi   — modify profile fields (--lingvo, etc.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from A import tr, tr_multi
from A.console import console
from A.utils import info, error, success
from A.core.config import load_config, save_config, Config

app = typer.Typer(
    name="uzanto",
    help=tr_multi(
        "Uzanto — administri uzantprofilon",
        "User — manage user profile",
        "Utilisateur — gérer le profil utilisateur",
    ),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


@app.command("vidi")
def vidi() -> None:
    """View current user profile configuration."""
    cfg = load_config()

    table = Table(show_header=False, box=None)
    table.add_column(tr_multi("Kampo", "Field", "Champ"), style="dim")
    table.add_column(tr_multi("Valoro", "Value", "Valeur"))

    table.add_row(tr_multi("Lingvo", "Language", "Langue"), cfg.language or "-")
    table.add_row(tr_multi("Dosiero", "Config file", "Fichier"), str(config_path()))

    console.print(table)


@app.command("modifi")
def modifi(
    lingvo: Optional[str] = typer.Option(
        None,
        "--lingvo",
        "-l",
        help=tr_multi(
            "Lingva kodo (ekz: eo, en, fr)",
            "Language code (e.g. eo, en, fr)",
            "Code de langue (ex: eo, en, fr)",
        ),
    ),
) -> None:
    """Modify user profile settings."""
    cfg = load_config()
    changed = False

    if lingvo is not None:
        if len(lingvo) != 2 or not lingvo.isalpha():
            error(tr_multi(
                f"Nevalida lingvokodo: '{lingvo}'. Uzu 2-literan kodon (ekz: eo, en, fr).",
                f"Invalid language code: '{lingvo}'. Use a 2-letter code (e.g. eo, en, fr).",
                f"Code de langue invalide : '{lingvo}'. Utilisez un code à 2 lettres (ex: eo, en, fr).",
            ))
            raise typer.Exit(1)
        cfg.language = lingvo.lower()
        changed = True
        info(tr_multi(
            f"Lingvo agordita al: {lingvo}",
            f"Language set to: {lingvo}",
            f"Langue définie sur : {lingvo}",
        ))

    if not changed:
        info(tr_multi(
            "Neniuj ŝanĝoj. Uzu 'A uzanto modifi --lingvo <kodo>' por agordi lingvon.",
            "No changes. Use 'A uzanto modifi --lingvo <code>' to set language.",
            "Aucun changement. Utilisez 'A uzanto modifi --lingvo <code>' pour définir la langue.",
        ))
        return

    save_config(cfg)
    success(tr_multi(
        "Profilo ĝisdatigita.",
        "Profile updated.",
        "Profil mis à jour.",
    ))


def config_path() -> Path:
    """Return the path to the user config file."""
    from A.core.paths import config_dir
    return config_dir() / "config.toml"


__all__ = ["app"]
