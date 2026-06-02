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
from A.core.config import load_config, save_config
from A.core.paths import config_dir
from A.core.uzanto_service import (
    load_profile, save_profile,
    get_master_password, set_master_password, delete_master_password,
    get_huggingface_api_key, set_huggingface_api_key,
    encrypt_profile, decrypt_profile,
    validate_date, normalize_multi_contact,
    display_value, mask_api_key, _STANDARD_FIELDS,
)

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
def modifi(
    lingvo: Optional[str] = typer.Option(None, "--lingvo", "-l",
        help=_H("Lingva kodo (ekz: eo,en,fr)", "Language code (eo,en,fr)", "Code langue (ex: eo,en,fr)")),
    nomo: Optional[str] = typer.Option(None, "--nomo", "-n",
        help=_H("Nomo", "First name", "Prénom")),
    familia_nomo: Optional[str] = typer.Option(None, "--familia-nomo", "-fn",
        help=_H("Familia nomo", "Family name", "Nom famille")),
    naskig_dato: Optional[str] = typer.Option(None, "--naskig-dato", "-nd",
        help=_H("Naskiĝdato (YYYY-MM-DD)", "Birth date (YYYY-MM-DD)", "Date naissance (AAAA-MM-JJ)")),
    naskig_loko: Optional[str] = typer.Option(None, "--naskig-loko", "-nl",
        help=_H("Naskiĝloko", "Place of birth", "Lieu naissance")),
    lingvoj: Optional[str] = typer.Option(None, "--lingvoj", "-L",
        help=_H("Lingvoj (komo-disigitaj)", "Languages (comma-sep.)", "Langues (séparées par virgules)")),
    organizo: Optional[str] = typer.Option(None, "--organizo", "-o",
        help=_H("Organizo", "Organization", "Organisation")),
    organiza_identiga_numero: Optional[str] = typer.Option(None, "--organiza-identiga-numero", "-oin",
        help=_H("Org. identiga numero", "Org. identifier", "ID organisation")),
    telefonnumero: Optional[list[str]] = typer.Option(None, "--telefonnumero", "-tel",
        help=_H("Tel. formato valoro:etikedo:prima (ripetebla)", "Phone value:label:primary (repeatable)", "Tél. format valeur:étiquette:primaire")),
    retposhtadreso: Optional[list[str]] = typer.Option(None, "--retposhtadreso", "-ret",
        help=_H("Retposhto formato adreso:etikedo:prima (ripetebla)", "Email address:label:primary (repeatable)", "Email format adresse:étiquette:primaire")),
    api_slosilo_huggingface: Optional[str] = typer.Option(None, "--api-slosilo-huggingface", "-a",
        help=_H("HF API-ŝlosilo (konservita en keyring)", "HF API key (stored in keyring)", "Clé API HF (stockée keyring)")),
    kampo: Optional[list[str]] = typer.Option(None, "--kampo", "-k",
        help=_H("Propra kampo KEY:VALUE (ripetebla)", "Custom field KEY:VALUE (repeatable)", "Champ perso CLÉ:VALEUR (répétable)")),
) -> None:
    """Modify user profile fields."""
    cfg = load_config()
    profile = load_profile()
    changed = False

    # Language
    if lingvo is not None:
        if len(lingvo) != 2 or not lingvo.isalpha():
            error(_H(f"Nevalida lingvokodo: '{lingvo}'.",
                     f"Invalid language code: '{lingvo}'.",
                     f"Code langue invalide : '{lingvo}'."))
            raise typer.Exit(1)
        cfg.language = lingvo.lower()
        changed = True
        info(f"language → {lingvo}")

    # Simple string fields
    str_fields = {
        "nomo": nomo, "familia_nomo": familia_nomo,
        "naskig_dato": naskig_dato, "naskig_loko": naskig_loko,
        "organizo": organizo,
        "organiza_identiga_numero": organiza_identiga_numero,
    }
    for key, val in str_fields.items():
        if val is None:
            continue
        if key == "naskig_dato" and not validate_date(val):
            error(_H(f"Nevalida dato: '{val}'. Uzu YYYY-MM-DD.",
                     f"Invalid date: '{val}'. Use YYYY-MM-DD.",
                     f"Date invalide : '{val}'. Utilisez AAAA-MM-JJ."))
            raise typer.Exit(1)
        profile[key] = val
        changed = True
        info(f"{key} → {val}")

    # Languages list
    if lingvoj is not None:
        codes = [c.strip().lower() for c in lingvoj.split(",") if c.strip()]
        valid = [c for c in codes if len(c) == 2 and c.isalpha()]
        if valid:
            profile["lingvoj"] = valid
            changed = True
            info(f"lingvoj → {', '.join(valid)}")

    # Phone numbers (structured)
    if telefonnumero is not None:
        try:
            profile["telefonnumeroj"] = normalize_multi_contact(telefonnumero, kind="telefono")
            changed = True
            info(f"telefonnumeroj → {len(telefonnumero)} entriĝoj")
        except ValueError as exc:
            error(str(exc))
            raise typer.Exit(1)

    # Email addresses (structured)
    if retposhtadreso is not None:
        try:
            profile["retposhtadresoj"] = normalize_multi_contact(retposhtadreso, kind="retposhto")
            changed = True
            info(f"retposhtadresoj → {len(retposhtadreso)} entriĝoj")
        except ValueError as exc:
            error(str(exc))
            raise typer.Exit(1)

    # HuggingFace API key (keyring)
    if api_slosilo_huggingface is not None:
        if api_slosilo_huggingface.strip():
            set_huggingface_api_key(api_slosilo_huggingface.strip())
            profile["api_slosilo_huggingface"] = True
            info(_H("HF API-ŝlosilo konservita.", "HF API key saved.", "Clé API HF enregistrée."))
        else:
            delete_master_password()
            profile.pop("api_slosilo_huggingface", None)
            info(_H("HF API-ŝlosilo forigita.", "HF API key removed.", "Clé API HF supprimée."))
        changed = True

    # Custom fields (kampoj)
    if kampo:
        if "kampoj" not in profile or not isinstance(profile["kampoj"], dict):
            profile["kampoj"] = {}
        for entry in kampo:
            if ":" not in entry:
                error(_H(f"Nevalida formato: '{entry}'. Uzu KEY:VALUE.",
                         f"Invalid format: '{entry}'. Use KEY:VALUE.",
                         f"Format invalide : '{entry}'. Utilisez CLÉ:VALEUR."))
                raise typer.Exit(1)
            k, _, v = entry.partition(":")
            profile["kampoj"][k.strip()] = v.strip()
            changed = True
            info(f"kampo {k.strip()} → {v.strip()}")

    if not changed:
        info(_H("Neniuj ŝanĝoj. Uzu --help por opcioj.",
                "No changes. Use --help for options.",
                "Aucun changement. Utilisez --help."))
        return

    # Merge profile into cfg.settings and save once (avoids double-save bug)
    cfg.settings.clear()
    cfg.settings.update(profile)
    save_config(cfg)
    success(_H("Profilo ĝisdatigita.", "Profile updated.", "Profil mis à jour."))


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
        cfg.settings.clear()
        cfg.settings.update(data["profile"])
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
