"""Internationalization for A - Esperanto-native."""

from typing import Callable

# Translations - Esperanto as primary
_translations = {
    "eo": {
        # Core
        "success": "Sukceso",
        "error": "Eraro",
        "warning": "Averto",
        "not_found": "Ne trovita",
        "help": "Helpo",
        "A - minimuma CLI kadro": "A - minimuma CLI kadro",
        # sistemo
        "system_info": "Sistemaj informoj",
        "os": "Operaciumo",
        "cpu": "CPU",
        "ram": "RAM",
        "storage": "Stoko",
        "battery": "Baterio",
        "network": "Reto",
        "bluetooth": "Blututo",
        "neniuj": "Neniuj",
        # wifi
        "wifi": "Wi-Fi",
        "wifi_networks": "Wi-Fi Retoj",
        "connect": "Konekti",
        "disconnect": "Malkonekti",
        "forget": "Forigi",
        "connected": "Konektita",
        "disconnected": "Malkonektita",
        "signal": "Signalforto",
        "security": "Sekureco",
        "status": "Statuso",
        "ssid": "SSID",
        "password": "Pasvorto",
        # bluetooth
        "bluetooth_devices": "Blututaj Aparatoj",
        "paired_devices": "Paregitaj Aparatoj",
        "mac": "MAC",
        "no_devices": "Neniuj aparatoj trovita",
        "nomo": "Nomo",
        "statuso": "Statuso",
        # Missing translations used in CLI
        "konektita": "Konektita",
        "malkonektita": "Malkonektita",
        # usb
        "usb_devices": "USB Aparatoj",
        "bus": "Bus",
        "device": "Aparato",
        "vendor": "ID",
        "loko": "Loko",
        # disko
        "disks": "Diskoj",
        "disk": "Disko",
        "mount": "Munti",
        "unmount": "Malmunti",
        "mounted": "Muntita",
        "unmounted": "Malmuntita",
        "health": "Sano",
        "size": "Grandeco",
        "type": "Tipo",
        "model": "Modelo",
        # rubo
        "trash": "Rubujo",
        "trash_empty": "La rubujo estas malplena",
        "moved_to_trash": "Al rubujo",
        "deleted": "Forigita",
        "restored": "Restarigita",
        "permanent": "Ĉapele forigita",
        "definitiva": "Definitiva",
        "files": "Dosieroj",
        "destination": "Celo",
        # bash-alias
        "bash_aliases": "Bash-aliasoj",
        "alias": "Alias",
        "function": "Funkcio",
        "notes": "Notoj",
        "added": "Aldonita",
        "modified": "Modifita",
        "deleted_alias": "Forigita",
        "created_at": "Kreita",
        # particio
        "partition": "Particio",
        "shrink": "Malpligrandigi",
        "create_partition": "Krei particion",
        "format": "Formati",
        # Missing from CLI modules
        "pareigitaj_aparoj": "Pareigitaj Aparatoj",
        "konektita_al": "Konektita al",
        "neniu_usb": "Neniuj USB aparatoj",
        "usb_aparoj": "USB Aparatoj",
        "neniu_diskoj": "Neniuj diskoj",
        "disko": "Disko",
        "muntita_": "Muntita:",
        "malmuntita_": "Malmuntita:",
        "neniu_aliasoj": "Neniuj aliasoj",
        "uid_aldonita": "Aldonita: UID",
        "ne_trovita_uid": "Ne trovita: UID",
        "sukcese": "Sukcese",
        "malsukcese": "Malsukcese",
        # bash-alias more
        "alfabetaordo": "Alfabetaordo",
        "inversaordo": "Inversaordo",
        "sen_konfirmo": "Sen konfirmo",
        "sercho_termino": "Serĉo termino",
    },
    "en": {
        # Core
        "success": "Success",
        "error": "Error",
        "warning": "Warning",
        "not_found": "Not found",
        "help": "Help",
        "A - minimuma CLI kadro": "A - minimal CLI framework",
        # sistemo
        "system_info": "System Information",
        "os": "OS",
        "cpu": "CPU",
        "ram": "RAM",
        "storage": "Storage",
        "battery": "Battery",
        "network": "Network",
        "bluetooth": "Bluetooth",
        "neniuj": "None",
        # wifi
        "wifi": "Wi-Fi",
        "wifi_networks": "Wi-Fi Networks",
        "connect": "Connect",
        "disconnect": "Disconnect",
        "forget": "Forget",
        "connected": "Connected",
        "disconnected": "Disconnected",
        "signal": "Signal",
        "security": "Security",
        "status": "Status",
        "ssid": "SSID",
        "password": "Password",
        # bluetooth
        "bluetooth_devices": "Bluetooth Devices",
        "paired_devices": "Paired Devices",
        "mac": "MAC",
        "no_devices": "No devices found",
        # usb
        "usb_devices": "USB Devices",
        "bus": "Bus",
        "device": "Device",
        "vendor": "ID",
        # disko
        "disks": "Disks",
        "disk": "Disk",
        "mount": "Mount",
        "unmount": "Unmount",
        "mounted": "Mounted",
        "unmounted": "Unmounted",
        "health": "Health",
        "size": "Size",
        "type": "Type",
        "model": "Model",
        # rubo
        "trash": "Trash",
        "trash_empty": "Trash is empty",
        "moved_to_trash": "Moved to trash",
        "deleted": "Deleted",
        "restored": "Restored",
        "permanent": "Permanently deleted",
        "definitiva": "Permanent",
        "files": "Files",
        "destination": "Destination",
        # bash-alias
        "bash_aliases": "Bash Aliases",
        "alias": "Alias",
        "function": "Function",
        "notes": "Notes",
        "added": "Added",
        "modified": "Modified",
        "deleted_alias": "Deleted",
        "created_at": "Created",
        # particio
        "partition": "Partition",
        "shrink": "Shrink",
        "create_partition": "Create partition",
        "format": "Format",
        # Missing from CLI modules
        "pareigitaj_aparoj": "Paired Devices",
        "konektita_al": "Connected to",
        "neniu_usb": "No USB devices",
        "usb_aparoj": "USB Devices",
        "neniu_diskoj": "No disks",
        "disko": "Disk",
        "muntita_": "Mounted:",
        "malmuntita_": "Unmounted:",
        "neniu_aliasoj": "No aliases",
        "uid_aldonita": "Added: UID",
        "ne_trovita_uid": "Not found: UID",
        "sukcese": "Success",
        "malsukcese": "Failed",
        # bash-alias more
        "alfabetaordo": "Alphabetical order",
        "inversaordo": "Reverse order",
        "sen_konfirmo": "No confirmation",
        "sercho_termino": "Search term",
    },
    "fr": {
        # Core
        "success": "Succès",
        "error": "Erreur",
        "warning": "Avertissement",
        "not_found": "Non trouvé",
        "help": "Aide",
        "A - minimuma CLI kadro": "A - Cadre CLI minimal",
        # sistemo
        "system_info": "Informations système",
        "os": "SE",
        "cpu": "CPU",
        "ram": "RAM",
        "storage": "Stockage",
        "battery": "Batterie",
        "network": "Réseau",
        "bluetooth": "Bluetooth",
        "neniuj": "Aucun",
        # wifi
        "wifi": "Wi-Fi",
        "wifi_networks": "Réseaux Wi-Fi",
        "connect": "Connecter",
        "disconnect": "Déconnecter",
        "forget": "Supprimer",
        "connected": "Connecté",
        "disconnected": "Déconnecté",
        "signal": "Signal",
        "security": "Sécurité",
        "status": "Statut",
        "ssid": "SSID",
        "password": "Mot de passe",
        # bluetooth
        "bluetooth_devices": "Appareils Bluetooth",
        "paired_devices": "Appareils appariés",
        "mac": "MAC",
        "no_devices": "Aucun appareil trouvé",
        # usb
        "usb_devices": "Appareils USB",
        "bus": "Bus",
        "device": "Appareil",
        "vendor": "ID",
        # disko
        "disks": "Disques",
        "disk": "Disque",
        "mount": "Monter",
        "unmount": "Démonter",
        "mounted": "Monté",
        "unmounted": "Démonté",
        "health": "Santé",
        "size": "Taille",
        "type": "Type",
        "model": "Modèle",
        # rubo
        "trash": "Corbeille",
        "trash_empty": "La corbeille est vide",
        "moved_to_trash": "Déplacé vers la corbeille",
        "deleted": "Supprimé",
        "restored": "Restauré",
        "permanent": "Définitivement supprimé",
        "definitiva": "Permanent",
        "files": "Fichiers",
        "destination": "Destination",
        # bash-alias
        "bash_aliases": "Alias Bash",
        "alias": "Alias",
        "function": "Fonction",
        "notes": "Notes",
        "added": "Ajouté",
        "modified": "Modifié",
        "deleted_alias": "Supprimé",
        "created_at": "Créé",
        # particio
        "partition": "Partition",
        "shrink": "Réduire",
        "create_partition": "Créer partition",
        "format": "Formater",
        # Missing from CLI modules
        "pareigitaj_aparoj": "Appareils appariés",
        "konektita_al": "Connecté à",
        "neniu_usb": "Aucun appareil USB",
        "usb_aparoj": "Appareils USB",
        "neniu_diskoj": "Aucun disque",
        "disko": "Disque",
        "muntita_": "Monté:",
        "malmuntita_": "Démonté:",
        "neniu_aliasoj": "Aucun alias",
        "uid_aldonita": "Ajouté: UID",
        "ne_trovita_uid": "Non trouvé: UID",
        "sukcese": "Succès",
        "malsukcese": "Échec",
        # bash-alias more
        "alfabetaordo": "Ordre alphabétique",
        "inversaordo": "Ordre inverse",
        "sen_konfirmo": "Sans confirmation",
        "sercho_termino": "Terme de recherche",
    },
}

_current_lang = "eo"  # Esperanto as default


def set_language(lang: str) -> None:
    """Set the current language."""
    global _current_lang
    if lang not in _translations:
        raise ValueError(f"Unsupported language: {lang}")
    _current_lang = lang


def tr(key: str, lang: str = None) -> str:
    """Translate a key. Falls back to English then key."""
    if lang is None:
        lang = _current_lang
    
    # Try current language first
    if key in _translations.get(lang, {}):
        return _translations[lang][key]
    
    # Fall back to English
    if key in _translations.get("en", {}):
        return _translations["en"][key]
    
    # Fall back to key itself
    return key


def tr_multi(eo: str, en: str = None, fr: str = None) -> str:
    """Return translation for current language from inline translations.

    This provides a quick way to add inline translations without a dictionary.
    Falls back: eo -> en -> eo.
    """
    translations = {"eo": eo, "en": en or eo, "fr": fr or en or eo}
    current = _translations.get(_current_lang, {})
    return translations.get(_current_lang, eo)


def available_languages() -> list[str]:
    """Return list of available language codes."""
    return list(_translations.keys())


def get_current_language() -> str:
    """Return the current language."""
    return _current_lang