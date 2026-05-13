"""Uzanto — user profile management CLI, ported from autish-legacy.

Usage:
    A uzanto vidi              — view profile
    A uzanto modifi            — modify profile fields
    A uzanto eksporti <file>   — export profile to JSON
    A uzanto importi <file>    — import profile from JSON
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from A import tr, tr_multi
from A.console import console
from A.utils import info, error, success
from A.core.config import load_config, save_config

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

# Standard profile fields (stored in config settings)
# Matching autish-legacy: nomo, familia_nomo, naskig_dato, lingvoj, ...
_PROFILE_FIELDS: tuple[str, ...] = (
    "nomo", "familia_nomo", "naskig_dato", "naskig_loko",
    "lingvoj", "organizo", "telefonnumeroj", "retposhtadresoj",
)


def _cfg_path() -> Path:
    """Return path to user config file."""
    from A.core.paths import config_dir
    return config_dir() / "config.toml"


def _display_val(val: object) -> str:
    """Format a profile value for display."""
    if val is None:
        return "-"
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val)


@app.command("vidi")
def vidi() -> None:
    """View current user profile configuration."""
    cfg = load_config()

    table = Table(show_header=False, box=None)
    table.add_column(tr_multi("Kampo", "Field", "Champ"), style="bold")
    table.add_column(tr_multi("Valoro", "Value", "Valeur"))

    # Core config fields
    table.add_row(tr_multi("Lingvo", "Language", "Langue"), cfg.language or "-")
    table.add_row(tr_multi("Dosiero", "Config file", "Fichier"), str(_cfg_path()))

    # Profile fields (from settings)
    for field in _PROFILE_FIELDS:
        val = cfg.settings.get(field)
        if val is not None:
            table.add_row(field, _display_val(val))

    console.print(table)


@app.command("modifi")
def modifi(
    lingvo: Optional[str] = typer.Option(
        None, "--lingvo", "-l",
        help=tr_multi("Lingva kodo (ekz: eo, en, fr)", "Language code (e.g. eo, en, fr)", "Code de langue (ex: eo, en, fr)"),
    ),
    nomo: Optional[str] = typer.Option(
        None, "--nomo", "-n",
        help=tr_multi("Nomo", "First name", "Prénom"),
    ),
    familia_nomo: Optional[str] = typer.Option(
        None, "--familia-nomo", "-fn",
        help=tr_multi("Familia nomo", "Family name", "Nom de famille"),
    ),
    naskig_dato: Optional[str] = typer.Option(
        None, "--naskig-dato", "-nd",
        help=tr_multi("Naskiĝdato (YYYY-MM-DD)", "Date of birth (YYYY-MM-DD)", "Date de naissance (AAAA-MM-JJ)"),
    ),
    naskig_loko: Optional[str] = typer.Option(
        None, "--naskig-loko", "-nl",
        help=tr_multi("Naskiĝloko", "Place of birth", "Lieu de naissance"),
    ),
    lingvoj: Optional[str] = typer.Option(
        None, "--lingvoj", "-L",
        help=tr_multi("Lingvoj (komo-disigitaj, ekz: eo,en,fr)", "Languages (comma-separated, e.g. eo,en,fr)", "Langues (séparées par des virgules, ex: eo,en,fr)"),
    ),
    organizo: Optional[str] = typer.Option(
        None, "--organizo", "-o",
        help=tr_multi("Organizo", "Organization", "Organisation"),
    ),
) -> None:
    """Modify user profile settings."""
    cfg = load_config()
    changed = False

    # Core config fields
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
        info(tr_multi(f"Lingvo → {lingvo}", f"Language → {lingvo}", f"Langue → {lingvo}"))

    # Profile fields (stored in settings)
    _str_fields = {
        "nomo": nomo, "familia_nomo": familia_nomo,
        "naskig_dato": naskig_dato, "naskig_loko": naskig_loko,
        "organizo": organizo,
    }
    for key, val in _str_fields.items():
        if val is not None:
            cfg.settings[key] = val
            changed = True
            info(f"{key} → {val}")

    if lingvoj is not None:
        codes = [c.strip().lower() for c in lingvoj.split(",") if c.strip()]
        valid = [c for c in codes if len(c) == 2 and c.isalpha()]
        if valid:
            cfg.settings["lingvoj"] = valid
            changed = True
            info(tr_multi(
                f"Lingvoj → {', '.join(valid)}",
                f"Languages → {', '.join(valid)}",
                f"Langues → {', '.join(valid)}",
            ))

    if not changed:
        info(tr_multi(
            "Neniuj ŝanĝoj. Uzu 'A uzanto modifi --help' por vidi opciojn.",
            "No changes. Use 'A uzanto modifi --help' to see options.",
            "Aucun changement. Utilisez 'A uzanto modifi --help' pour voir les options.",
        ))
        return

    save_config(cfg)
    success(tr_multi("Profilo ĝisdatigita.", "Profile updated.", "Profil mis à jour."))


@app.command("eksporti")
def eksporti(
    celo: str = typer.Argument(
        ...,
        help=tr_multi("Eliga JSON-dosiero", "Output JSON file", "Fichier JSON de sortie"),
    ),
) -> None:
    """Export user profile to JSON file."""
    cfg = load_config()
    profile = {
        "language": cfg.language,
        "profile": {f: cfg.settings.get(f) for f in _PROFILE_FIELDS if cfg.settings.get(f) is not None},
    }
    path = Path(celo).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    success(tr_multi(
        f"Profielo eksportita al {path}",
        f"Profile exported to {path}",
        f"Profil exporté vers {path}",
    ))


@app.command("importi")
def importi(
    fonto: str = typer.Argument(
        ...,
        help=tr_multi("Eniga JSON-dosiero", "Input JSON file", "Fichier JSON d'entrée"),
    ),
) -> None:
    """Import user profile from JSON file."""
    path = Path(fonto).expanduser().resolve()
    if not path.exists():
        error(tr_multi(
            f"Dosiero ne trovita: {path}",
            f"File not found: {path}",
            f"Fichier non trouvé: {path}",
        ))
        raise typer.Exit(1)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        error(str(e))
        raise typer.Exit(1)

    cfg = load_config()
    if "language" in data:
        cfg.language = data["language"]
    if "profile" in data and isinstance(data["profile"], dict):
        cfg.settings.update(data["profile"])
    save_config(cfg)

    success(tr_multi(
        f"Profielo importita el {path}",
        f"Profile imported from {path}",
        f"Profil importé depuis {path}",
    ))


__all__ = ["app"]
