# Wikibase QuickStatements API Importer

Kleines, robustes Tool, um QuickStatements-ähnliche **Item-Statements** per
Wikibase-/MediaWiki-Action-API in eine Wikibase-Instanz zu schreiben – inklusive
**föderierter Wikidata-Properties und -Items**.

## Projektstruktur

```
wikibase-federation/
├── main.py                 # Startpunkt (das hier ausführen)
├── config.ini              # deine Konfiguration (gitignored) – aus config.example.ini
├── config.example.ini      # Vorlage
├── wbqs/                    # der Paketcode
│   ├── parser.py           #   QS-Parsing (netzwerkfrei, getestet)
│   ├── client.py           #   Wikibase-API-Client
│   ├── config.py           #   Config + Job-/Testfall-Auflösung
│   └── importer.py         #   Ablauf (Login, Schreiben, Report)
├── testcases/              # je Testfall ein Ordner …
│   └── example/
│       ├── input.qs        #   die QS-Daten dieses Falls
│       └── report/         #   Reports dieses Falls (wird angelegt, gitignored)
└── tests/                  # Unit-Tests des Parsers
```

**Idee:** Der Code liegt im Paket `wbqs/`, die Daten in `testcases/`. Über einen
Zeiger in `config.ini` wählst du, welcher Testfall gerade importiert wird. Für
einen neuen Fall einfach `testcases/mein-fall/input.qs` anlegen und in der Config
`testcase = testcases/mein-fall` setzen.

## Warum die API und nicht QuickStatements?

Ziel ist die **Ontology-Federation** von Wikibase. Zwei Spielarten:

- **Federated Values** – lokale Property, *Wikidata-Item* als Wert.
- **Federated Properties** – die *Property selbst* kommt von Wikidata.

Die API-Repräsentation föderierter Entitäten ist noch Alpha, weshalb
QuickStatements damit (noch) nicht umgeht. Der direkte Aufruf `wbcreateclaim`
mit der vollen Entity-URI funktioniert dagegen – als Wert (`id`) und, für
föderierte Properties, als `property`-Parameter:

```json
{ "property": "http://www.wikidata.org/entity/P5572",
  "value":    {"entity-type": "item", "id": "http://www.wikidata.org/entity/Q5"} }
```

## Eingabeformat

Drei Spalten (Tab- oder Whitespace-getrennt): `<Subjekt> <Property> <Wert>`.
Leerzeilen und `#`-Zeilen werden ignoriert.

- **Subjekt**: immer ein **lokales** Item (`Q…`).
- **Property**: lokal (`P…`) **oder** föderiert (`wd:P…` bzw. Wikidata-URI).
- **Wert**: lokales Item (`Q…`) **oder** föderiert (`wd:Q…` bzw. Wikidata-URI).

Alle vier Kombinationen sind möglich:

```text
Q3  P1        Q4        # lokale Property    + lokaler Item-Wert
Q3  P1        wd:Q5     # lokale Property    + föderierter Item-Wert
Q3  wd:P5572  Q4        # föderierte Property + lokaler Item-Wert
Q3  wd:P5572  wd:Q5     # föderierte Property + föderierter Item-Wert
```

Föderierte Referenzen werden zur Entity-URI normalisiert
(`http://www.wikidata.org/entity/…`). Für Properties werden `wd:P…`, `wdt:P…`,
`…/entity/P…` und `…/prop/direct/P…` akzeptiert.

**Nicht** enthalten: Strings, Datums-/Mengenangaben, Koordinaten, Qualifier,
References, Labels, Descriptions, Aliases. Fokus: `wikibase-item`.

## Voraussetzungen

- Python 3.9+ und Git.
- Ziel-Wikibase mit aktivierter Ontology-Federation; für föderierte Werte eine
  `wikibase-item`-Property, die föderierte Werte erlaubt; für föderierte
  Properties muss Property Federation aktiv sein.
- Ein **Bot-Passwort** (`Special:BotPasswords`); Benutzer = `Hauptkonto@botname`.

## Schnellstart

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell):
# .\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp config.example.ini config.ini      # Windows: copy config.example.ini config.ini
# config.ini ausfüllen: api_url, username (Konto@bot), password, user_agent
```

Testfall vorbereiten und importieren:

1. QS-Daten in `testcases/example/input.qs` legen (oder einen neuen Ordner
   `testcases/<name>/input.qs` anlegen und in `config.ini` `testcase` darauf zeigen).
2. **Trockenlauf** (schreibt nichts, solange `dry_run = true`):

   ```bash
   python main.py
   ```

3. **Scharfschalten**: in `config.ini` `dry_run = false`, dann erneut `python main.py`.

Reports landen als `testcases/<name>/report/import_report_<zeitstempel>.json`.

### In VS Code

`main.py` läuft **ohne Argumente** – also per Play-Button oben rechts oder
Rechtsklick → **„Run Python File in Terminal"**. Der Job kommt aus `config.ini`.
Fehlt `config.ini`, wird `config.example.ini` genutzt und ein **erzwungener
Dry-Run** gefahren. Über **Run and Debug** (F5) gibt es drei Starts: Dry-Run des
Config-Jobs, echter Lauf des Config-Jobs, und ein Lauf der **gerade offenen**
`.qs`-Datei (Dry-Run, `--limit 1`).

## Config-Referenz (`config.ini`)

```ini
[wikibase]
api_url    = https://federated-objects.de/w/api.php
username   = Fthierygeo@importbot
password   = DEIN_BOT_PASSWORT
user_agent = wikibase-qs-api-importer/1.1 (du@example.org)

[job]
testcase = testcases/example      ; Ordner mit der .qs-Datei; Reports -> <ordner>/report
; qs_file = testcases/example/input.qs   ; alternativ direkt eine Datei (hat Vorrang)

[import]
dry_run          = true
skip_existing    = true
maxlag           = 0
mark_bot         = false
throttle_seconds = 0.0
```

Relative Pfade werden **relativ zur `config.ini`** aufgelöst (funktioniert also
unabhängig vom Arbeitsverzeichnis). Zugangsdaten können auch per Umgebungsvariable
kommen (`WIKIBASE_USERNAME`, `WIKIBASE_PASSWORD`; haben Vorrang, umgehen die
INI-`%`-Interpolation).

## Nutzung mit Argumenten

```bash
python main.py testcases/example              # Testfall-Ordner explizit
python main.py testcases/example/input.qs     # bestimmte Datei
python main.py --dry-run                       # nie schreiben
python main.py --limit 1                       # nur erste Zeile (guter erster Test)
python main.py --federate-bare-qids            # bare Q-IDs als Wikidata-Items
python main.py --federate-bare-pids            # bare P-IDs als Wikidata-Properties
python main.py --no-skip-existing --verbose
```

## Verhalten & Sicherheitsnetze

- **Duplikatprüfung** (`skip_existing`): identische Property + identischer Wert
  werden übersprungen.
- **User-Agent**, **`assert=user`**, optionales **`maxlag`**,
  **`badtoken`-Erneuerung**, **GET-Retries**, **Throttling**.
- **Report** je Lauf im `report/` des Testfalls.
- **Exit-Codes**: `0` = Erfolg, `1` = mind. ein Schreibfehler, `2` =
  Parsing-/Konfigurationsfehler.

Zwei Annahmen bei föderierten Properties (falls die Instanz abweicht, siehst du
es als klaren API-Fehler bzw. als nicht erkanntes Duplikat): der `property`-
Parameter erhält die Entity-URI, und `skip_existing` setzt voraus, dass
`wbgetentities` den Claim unter demselben URI-Schlüssel zurückgibt.

## Sicherheit

- `config.ini` niemals committen (steht in `.gitignore`).
- Bevorzugt **Bot-Passwörter** (bestehen nur aus Buchstaben/Ziffern).
- **Jedes je in einem Chat/Skript sichtbare Passwort widerrufen.**

## Entwicklung

```bash
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

Optionaler Editable-Install stellt den Befehl `wb-qs-import` bereit:

```bash
pip install -e .
wb-qs-import --dry-run
```

## Lizenz

MIT – siehe `LICENSE` (Namensfeld anpassen).
