# A Dokumentado

Bonvenon al A — minimuma CLI kadro

## Rapida Komenco

### Instalo

```bash
pip install A-core
```

Aŭ el fontkodo:

```bash
git clone https://github.com/Ron-RONZZ-org/A-core.git
cd A-core
poetry install
```

### Baza Uzado

```bash
A --help          # Montri helpon
A list            # Listigi kromprogramojn
A help            # Montri helpon
```

### Instali Kromprogramojn

```bash
pip install A-tempo      # Tempo
pip install A-sistemo     # Sistemo
pip install A-mail       # Retpoŝto (kiam havebla)
```

Aŭ ĉiuj kromprogramoj:

```bash
pip install A-core[all]
```

---

## Arkitekturo

A havas kvar tavolojn kun strikta dependodirekto:

```
┌─────────────────────────────────────────────┐
│ CLI Tavo (komandoj)                │
│ Typer komandoj, argumentoj           │
├─────────────────────────────────────────────┤
│ Serva Tavo                       │
│ Negoca logiko                  │
├─────────────────────────────────────────────┤
│ Datuma Tavo                     │
│ SQLite repos                  │
├─────────────────────────────────────────────┤
│ Kerna Tavo                     │
│ Agordo, vojoj, i18n, tipoj    │
└─────────────────────────────────────────────┘
```

**Regulo:** CLI → Service → Data → Core. Neniu inversa dependoj.

---

## Evoligi Kromprogramojn

### Baza Kromprograma Strukturo

```python
# A_tempo/src/A_tempo/cli.py
import typer
from A import data_dir, ensure_dirs

app = typer.Typer(name="tempo", help="Tempogestado")

@app.command()
def now():
    """Montri aktuala tempo."""
    from datetime import datetime
    from A.utils import success
    
    ensure_dirs()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success(now)

__all__ = ["app"]
```

### Kromprograma Registrado

En via `pyproject.toml`:

```toml
[project.entry-points."A.commands"]
tempo = "A_tempo.cli:app"
```

### Datuma Tavo

Uz `A.data.SQLiteDB`:

```python
from A.data import SQLiteDB
from A.core.paths import data_dir

class TempoDB(SQLiteDB):
    def __init__(self):
        super().__init__("tempo", {
            "eventoj": """
                CREATE TABLE eventoj (
                    id INTEGER PRIMARY KEY,
                    nomo TEXT NOT NULL,
                    kreita TEXT NOT NULL
                )
            """
        })
```

---

## Agordo

A serĉas agordon ĉe `~/.config/A/config.toml`:

```toml
[A]
language = "eo"        # Defaŭlto: Esperanto
verbose = false

[A.aliases]
t = "tempo"
```

---

## Lingva Subteno

A subtenas tri lingvojn:

| Kodo | Lingvo |
|------|-------|
| `eo` | Esperanto (defaŭlto) |
| `en` | English |
| `fr` | Français |

Ŝanĝi lingvon:

```python
from A.core.i18n import set_language
set_language("en")
```

---

## API Referenco

### Kerno

```python
from A import tr, ensure_dirs
from A.core import data_dir, config_dir, load_config
```

### Datumo

```python
from A.data import SQLiteDB
```

### Iloj

```python
from A.utils import success, error, info, run, edit_text
```

---

## Kontribuado

Vidu CONTRIBUTING.md en la deponejo radiko.

---

## Licenco

GPL-3.0-only