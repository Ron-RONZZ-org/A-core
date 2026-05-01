# A Documentation

Bienvenue dans A — Cadre CLI minimal

## Démarrage Rapide

### Installation

```bash
pip install A-core
```

Ou depuis le source:

```bash
git clone https://github.com/Ron-RONZZ-org/A-core.git
cd A-core
poetry install
```

### Utilisation de Base

```bash
A --help          # Afficher l'aide
A list            # Liste des plugins
A help            # Afficher l'aide
```

### Installer des Plugins

```bash
pip install A-tempo      # Temps
pip install A-sistemo     # Système
pip install A-mail       # Courriel (quand disponible)
```

Ou tous les plugins:

```bash
pip install A-core[all]
```

---

## Architecture

A a quatre couches avec direction de dépendance stricte:

```
┌─────────────────────────────────────────────┐
│ Couche CLI (commandes)               │
│ Commandes Typer,解析 des arguments    │
├─────────────────────────────────────────────┤
│ Couche Service                      │
│ Logique métier                 │
├─────────────────────────────────────────────┤
│ Couche Données                   │
│ Dépôts SQLite                │
├─────────────────────────────────────────────┤
│ Couche Core                     │
│ Config, chemins, i18n, types    │
└─────────────────────────────────────────────┘
```

**Règle:** CLI → Service → Data → Core. Pas de dépendances inverses.

---

## Développer des Plugins

### Structure de Plugin de Base

```python
# A_tempo/src/A_tempo/cli.py
import typer
from A import data_dir, ensure_dirs

app = typer.Typer(name="temps", help="Gestion du temps")

@app.command()
def maintenant():
    """Afficher l'heure actuelle."""
    from datetime import datetime
    from A.utils import success
    
    ensure_dirs()
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success(maintenant)

__all__ = ["app"]
```

### Enregistrement du Plugin

Dans votre `pyproject.toml`:

```toml
[project.entry-points."A.commands"]
temps = "A_temps.cli:app"
```

### Couche Données

Utilisez `A.data.SQLiteDB`:

```python
from A.data import SQLiteDB
from A.core.paths import data_dir

class TempsDB(SQLiteDB):
    def __init__(self):
        super().__init__("temps", {
            "evenements": """
                CREATE TABLE evenements (
                    id INTEGER PRIMARY KEY,
                    nom TEXT NOT NULL,
                    cree TEXT NOT NULL
                )
            """
        })
```

---

## Configuration

A cherche la configuration dans `~/.config/A/config.toml`:

```toml
[A]
language = "eo"        # Par défaut: Espéranto
verbose = false

[A.aliases]
t = "temps"
```

---

## Support Linguistique

A supporte trois langues:

| Code | Langue |
|------|-------|
| `eo` | Espéranto (par défaut) |
| `en` | English |
| `fr` | Français |

Changer la langue:

```python
from A.core.i18n import set_language
set_language("fr")
```

---

## Référence API

### Core

```python
from A import tr, ensure_dirs
from A.core import data_dir, config_dir, load_config
```

### Données

```python
from A.data import SQLiteDB
```

### Utilitaires

```python
from A.utils import success, error, info, run, edit_text
```

---

## Contribution

Voir CONTRIBUTING.md à la racine du dépôt.

---

## Licence

GPL-3.0-only