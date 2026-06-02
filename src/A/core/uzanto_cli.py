"""Uzanto — user profile management CLI, ported from autish-legacy.

Usage:
    A uzanto vidi                          — view profile
    A uzanto modifi [opcioj...]            — modify profile fields
    A uzanto eksporti <file> [--pasvorto]  — export profile
    A uzanto importi <file> [--pasvorto]   — import profile
    A uzanto pasvorto [--forigi]           — set/remove master password
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table
from rich.box import SIMPLE as BOX_SIMPLE

from A import tr, tr_multi
from A.console import console
from A.utils import info, error, success
from A.utils.editor import edit_file
from A.core.config import load_config, save_config, register_module_defaults, get_module_setting, set_module_setting
from A.core.paths import config_dir
from A.core.uzanto_service import (
    load_profile,
    get_master_password, set_master_password, delete_master_password,
    get_huggingface_api_key,
    encrypt_profile, decrypt_profile,
    display_value, mask_api_key, _STANDARD_FIELDS,
)

# Register uzanto config defaults so they appear as commented-out
# keys in the user's config.toml on first run.
register_module_defaults("uzanto", {
    "nomo":               ("", "Your given name"),
    "familia_nomo":       ("", "Your family name"),
    "naskig_dato":        ("", "Birth date (YYYY-MM-DD)"),
    "naskig_loko":        ("", "Place of birth"),
    "lingvo":             ("eo", "Interface language (eo/en/fr)"),
    "lingvoj":            (["eo"], "Languages you speak"),
    "organizo":           ("", "Organisation name"),
    "organiza_identiga_numero": ("", "Organisation ID number"),
    "telefonnumeroj":     ([], "Phone numbers (00<country><number>)"),
    "retposhtadresoj":    ([], "Email addresses"),
    "api_slosilo_huggingface": ("", "HuggingFace API key"),
})

_H = tr_multi  # short alias for the help-text helper
app = typer.Typer(
    name="uzanto",
    help=_H("Administri uzantprofilon", "Manage user profile", "Gérer le profil"),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help", "--helpo"]},
)


def _cfg_path() -> Path:
    return config_dir() / "config.toml"


# ── vidi ────────────────────────────────────────────────────────────────────


@app.command("vidi")
def vidi() -> None:
    """View current user profile configuration."""
    cfg = load_config()
    profile = load_profile()

    table = Table(show_header=False, box=BOX_SIMPLE)
    table.add_column(_H("Kampo", "Field", "Champ"), style="bold")
    table.add_column(_H("Valoro", "Value", "Valeur"))

    table.add_row(_H("Lingvo", "Language", "Langue"), cfg.language or "-")
    table.add_row(_H("Dosiero", "Config file", "Fichier"), str(_cfg_path()))

    pw = get_master_password()
    pw_s = _H("Agordita", "Set", "Défini") if pw else _H("Ne agordita", "Not set", "Non défini")
    table.add_row(_H("Ĉefpasvorto", "Master pwd", "Mdp maître"), pw_s)

    hf = get_huggingface_api_key()
    table.add_row("api_slosilo_huggingface", mask_api_key(hf) if hf else "-")

    for field in _STANDARD_FIELDS:
        if field == "api_slosilo_huggingface":
            continue
        val = profile.get(field)
        if val is not None:
            table.add_row(field, display_value(val))

    kampoj = profile.get("kampoj", {})
    if isinstance(kampoj, dict):
        for k, v in kampoj.items():
            table.add_row(f"[kampoj] {k}", str(v))
    console.print(table)


# ── modifi ──────────────────────────────────────────────────────────────────


@app.command("modifi")
def modifi() -> None:
    """Edit user profile in $EDITOR.

    Opens ``~/.config/A/config.toml`` in your preferred editor.
    Edit the ``[uzanto]`` section directly::

        [uzanto]
        nomo = "Alice"
        lingvoj = ["eo", "en"]

    Other modules also have their own sections (e.g. ``[filmeto]``)
    with commented defaults to guide you.

    Set ``$EDITOR`` to choose your editor (default: vim).
    """
    path = _cfg_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        save_config(load_config())  # create default

    if edit_file(path):
        success(_H("Agordilo savita. Rekomencu se necese.",
                   "Config saved. Restart if needed.",
                   "Configuration enregistrée. Redémarrez si nécessaire."))
    else:
        error(_H("Redaktado malsukcesis aŭ nuligita.",
                 "Edit failed or cancelled.",
                 "Édition échouée ou annulée."))


# ── eksporti ────────────────────────────────────────────────────────────────


@app.command("eksporti")
def eksporti(
    celo: str = typer.Argument(..., help=_H("Eliga dosiervojo", "Output path", "Chemin sortie")),
    pasvorto: Optional[str] = typer.Option(None, "--pasvorto", "-p",
        help=_H("Ĉifra pasvorto", "Encryption password", "Mot passe chiffrement")),
) -> None:
    """Export profile to JSON (optionally encrypted)."""
    cfg = load_config()
    profile = load_profile()
    data = {"language": cfg.language, "profile": profile}

    path = Path(celo).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    encrypt = pasvorto is not None
    if pasvorto is None:
        raw = typer.prompt(_H("Ĉu ĉifri? (j/N)", "Encrypt? (y/N)", "Chiffrer ? (o/N)"), default="n")
        encrypt = raw.strip().lower()[:1] in ("j", "y", "o")
        if encrypt:
            pasvorto = typer.prompt(_H("Pasvorto", "Password", "Mot passe"), hide_input=True, confirmation_prompt=True)

    if encrypt and pasvorto:
        blob = encrypt_profile(data, pasvorto)
        path.write_bytes(blob)
        status = _H("(ĉifrita)", "(encrypted)", "(chiffré)")
    else:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        status = _H("(necifrita)", "(plain)", "(non chiffré)")

    success(_H(f"Profielo eksportita al {path} {status}.",
               f"Profile exported to {path} {status}.",
               f"Profil exporté vers {path} {status}."))


# ── importi ─────────────────────────────────────────────────────────────────


@app.command("importi")
def importi(
    fonto: str = typer.Argument(..., help=_H("Eniga dosiervojo", "Input path", "Chemin entrée")),
    pasvorto: Optional[str] = typer.Option(None, "--pasvorto", "-p",
        help=_H("Malĉifra pasvorto", "Decryption password", "Mot passe déchiffrement")),
    anstatauigi: bool = typer.Option(False, "--anstatauigi", "-A",
        help=_H("Anstataŭigi sen konfirmo", "Overwrite w/o confirm", "Remplacer sans confirmer")),
) -> None:
    """Import profile from JSON (or encrypted) file."""
    path = Path(fonto).expanduser().resolve()
    if not path.exists():
        error(_H(f"Dosiero ne trovita: {path}", f"File not found: {path}", f"Fichier non trouvé: {path}"))
        raise typer.Exit(1)

    data: dict | None = None
    if pasvorto:
        data = _try_decrypt(path, pasvorto)
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pw = typer.prompt(_H("Ŝajnas ĉifrita. Pasvorto:", "Encrypted file. Password:", "Fichier chiffré. Mot passe :"), hide_input=True)
            if pw:
                data = _try_decrypt(path, pw)

    if not isinstance(data, dict):
        error(_H("Nevalida dosierformato.", "Invalid file format.", "Format fichier invalide."))
        raise typer.Exit(1)

    if load_profile() and not anstatauigi:
        typed = typer.prompt(
            _H("Tajpu 'anstataŭigi' por konfirmi", "Type 'overwrite' to confirm", "Tapez 'remplacer' pour confirmer")
        ).strip().lower()
        if typed not in ("anstataŭigi", "anstatauxigi", "overwrite", "remplacer"):
            info(_H("Nuligita.", "Cancelled.", "Annulé."))
            return

    cfg = load_config()
    if "language" in data:
        cfg.language = data["language"]
    if "profile" in data and isinstance(data["profile"], dict):
        cfg.module_settings["uzanto"] = dict(data["profile"])
        # Clean up legacy dot-notation keys
        for key in list(cfg.settings):
            if key.startswith("uzanto."):
                del cfg.settings[key]
    save_config(cfg)
    success(_H(f"Profielo importita el {path}", f"Profile imported from {path}", f"Profil importé depuis {path}"))


def _try_decrypt(path: Path, password: str) -> dict | None:
    """Attempt to decrypt and parse a profile file.

    Returns None if decryption fails.
    """
    try:
        raw = path.read_bytes()
        return decrypt_profile(raw, password)
    except Exception as e:
        error(_H(f"Malĉifrado malsukcesis: {e}", f"Decryption failed: {e}", f"Échec déchiffrement : {e}"))
        raise typer.Exit(1)


# ── pasvorto ────────────────────────────────────────────────────────────────


@app.command("pasvorto")
def pasvorto_cmd(
    forigi: bool = typer.Option(False, "--forigi", "-f",
        help=_H("Forigi la ĉefpasvorton", "Remove master password", "Supprimer mot passe maître")),
) -> None:
    """Set or remove the user master password (for profile encryption)."""
    old = get_master_password()

    if forigi:
        if not old:
            error(_H("Neniu ĉefpasvorto agordita.", "No master password set.", "Aucun mot passe maître."))
            raise typer.Exit(1)
        c = typer.prompt(_H("Tajpu 'konfirmi' por forigi", "Type 'confirm' to remove", "Tapez 'confirmer'")).strip()
        if c.lower() != "konfirmi":
            info(_H("Nuligita.", "Cancelled.", "Annulé."))
            return
        delete_master_password()
        success(_H("Ĉefpasvorto forigita.", "Master password removed.", "Mot passe maître supprimé."))
        return

    if old:
        e = typer.prompt(_H("Nuna ĉefpasvorto", "Current master password", "Mot passe actuel"), hide_input=True)
        if e != old:
            error(_H("Malĝusta pasvorto.", "Wrong password.", "Mot passe incorrect."))
            raise typer.Exit(1)

    new = typer.prompt(_H("Nova ĉefpasvorto", "New master password", "Nouveau mot passe"), hide_input=True, confirmation_prompt=True)
    if len(new) < 6:
        error(_H("Pasvorto ≥ 6 signoj.", "Password ≥ 6 chars.", "Mot passe ≥ 6 car."))
        raise typer.Exit(1)

    set_master_password(new)
    success(_H("Ĉefpasvorto agordita.", "Master password set.", "Mot passe maître défini."))


__all__ = ["app"]
