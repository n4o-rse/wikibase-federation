# Wikibase QuickStatements API Importer

Kleiner, robuster Workaround, um QuickStatements-ähnliche **Item-Statements** per
Wikibase-/MediaWiki-Action-API in eine Wikibase-Instanz zu schreiben – inklusive
**föderierter Wikidata-Items** als Statement-Wert.

- **Eingabedateien** (`*.qs`) liegen standardmäßig in **`/root/data`**.
- **Reports** werden standardmäßig nach **`/root/report`** geschrieben.
- Beide Pfade sind in `config.ini` überschreibbar (`data_dir`, `report_dir`).

## Warum die API und nicht QuickStatements?

Ziel ist die **Ontology-Federation- / „Federated-Values"**-Funktion von Wikibase:
Ein Statement-Wert ist ein *Wikidata-Item*, referenziert über seine volle
Entity-URI. Diese Funktion ist noch im Alpha-Stadium und ihre **API-Repräsentation
föderierter Items ist noch nicht fertig** – deshalb kommt QuickStatements damit
(noch) nicht zurecht, der direkte Aufruf `wbcreateclaim` mit der URI als `id`
funktioniert dagegen:

```json
{ "entity-type": "item", "id": "http://www.wikidata.org/entity/Q2016147" }
```

> Nicht mit den älteren „Federated **Properties**" verwechseln (dort kommen die
> *Properties* von Wikidata). Beide Funktionen setzen die passende Konfiguration
> und eine Allowlist auf der Zielinstanz voraus.

## Eingabeformat

Spalten Tab- oder Whitespace-getrennt, 3 Spalten. Leerzeilen und `#`-Zeilen
werden ignoriert.

```text
Q3  P1  Q4                                      # lokales Item -> lokales Item
Q3  P1  http://www.wikidata.org/entity/Q2016147 # lokales Item -> föderiertes Wikidata-Item
Q3  P1  wd:Q2016147                             # dito, Kurzschreibweise
```

**Bewusst nicht** enthalten: Strings, Datums-/Mengenangaben, Koordinaten,
Qualifier, References, Labels, Descriptions, Aliases. Fokus liegt auf
`wikibase-item`. Erweiterbar über `qs_parser.parse_value`.

## Voraussetzungen

- Python 3.9+ und Git.
- Ziel-Wikibase mit aktivierter Ontology-Federation und einer Property vom
  Datentyp `wikibase-item`, die föderierte Werte erlaubt (im Beispiel `P1`).
- Ein **Bot-Passwort** (`Special:BotPasswords`) mit Bearbeitungsrecht. Der
  Benutzername lautet dann `Hauptkonto@botname`.

## Schnellstart (Linux)

```bash
git clone <DEIN_REPO_URL> wikibase_qs_api_importer
cd wikibase_qs_api_importer

# 1) Virtuelle Umgebung + Abhängigkeiten
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) Verzeichnisse für Ein-/Ausgabe (report_dir wird sonst automatisch angelegt)
mkdir -p /root/data /root/report

# 3) Config anlegen und ausfüllen
cp config.example.ini config.ini
nano config.ini        # api_url, username (Konto@bot), password, user_agent

# 4) Eine .qs-Datei in /root/data ablegen (z. B. das Beispiel zum Testen)
cp example.qs /root/data/import.qs

# 5) Trockenlauf (schreibt nichts, solange dry_run = true)
python import_qs_api.py

# 6) Scharfschalten: in config.ini dry_run = false setzen, dann erneut:
python import_qs_api.py
```

Nach jedem echten Lauf liegt ein Bericht als
`/root/report/import_report_<zeitstempel>.json`.

## Config-Referenz (`config.ini`)

```ini
[wikibase]
api_url    = https://federated-objects.de/w/api.php
username   = Fthierygeo@importbot      ; Bot-Benutzer: Hauptkonto@botname
password   = DEIN_BOT_PASSWORT
user_agent = wikibase-qs-api-importer/1.0 (du@example.org)

[import]
data_dir         = /root/data          ; Ordner mit den .qs-Eingabedateien
report_dir       = /root/report        ; Ordner für die JSON-Reports
input_file       = import.qs           ; Datei in data_dir; leer = automatisch wählen
dry_run          = true                ; true = nur anzeigen, nichts schreiben
skip_existing    = true                ; vorhandene identische Statements überspringen
maxlag           = 0                   ; >0 nur bei repliziertem/geteiltem Backend nötig
mark_bot         = false               ; Edits mit Bot-Flag markieren (Bot-Recht nötig)
throttle_seconds = 0.0                 ; Pause zwischen Schreibvorgängen
```

Wie die Eingabedatei ohne CLI-Argument gefunden wird:

1. `[import] input_file` (in `data_dir`, sonst absoluter Pfad), sonst
2. die **einzige** `*.qs`-Datei in `data_dir` (bei mehreren: Fehlermeldung mit
   Auswahl), sonst
3. das mitgelieferte `example.qs` als Erst-Start-Fallback.

Zugangsdaten lassen sich alternativ per Umgebungsvariable setzen (haben Vorrang
vor der Datei, umgehen die INI-`%`-Interpolation):

```bash
export WIKIBASE_USERNAME="Fthierygeo@importbot"
export WIKIBASE_PASSWORD='dein"passwort'   # einfache Quotes: Sonderzeichen bleiben
```

## Nutzung mit Argumenten

```bash
python import_qs_api.py /root/data/import.qs         # bestimmte Datei
python import_qs_api.py --dry-run                    # nie schreiben
python import_qs_api.py --limit 1                    # nur erste Zeile (guter erster Test)
python import_qs_api.py --federate-bare-qids         # bare Q-IDs als Wikidata behandeln
python import_qs_api.py --no-skip-existing           # Duplikatprüfung aus
python import_qs_api.py --verbose                    # DEBUG-Ausgabe
```

## Windows / VS Code

Unter Windows die Pfade in `config.ini` anpassen, z. B. `data_dir = data` und
`report_dir = report` (relativ zum Projekt), Umgebung so aktivieren:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.ini config.ini
```

Das Skript läuft auch **ohne Argumente** und lässt sich damit per Play-Button
oben rechts oder Rechtsklick → **„Run Python File in Terminal"** starten. Fehlt
`config.ini`, wird `config.example.ini` genutzt und ein **erzwungener Dry-Run**
gefahren, sodass ein erster Klick sofort etwas Sinnvolles zeigt. Über
**Run and Debug** (F5) gibt es zwei vorkonfigurierte Starts (`.vscode/launch.json`):
ein reiner Dry-Run und ein Lauf mit der gerade geöffneten `.qs`-Datei.

## Verhalten & Sicherheitsnetze

- **Duplikatprüfung** (`skip_existing`): identische Property + identischer
  Item-Wert werden übersprungen.
- **User-Agent**, **`assert=user`**, optionales **`maxlag`**,
  **`badtoken`-Erneuerung**, **GET-Retries** und **Throttling** sind eingebaut.
- **Bericht** pro Lauf: `report_dir/import_report_<zeitstempel>.json`.
- **Exit-Codes**: `0` = Erfolg, `1` = mind. ein Schreibfehler, `2` =
  Parsing-/Konfigurationsfehler.

## Sicherheit

- `config.ini` niemals committen (steht in `.gitignore`).
- Bevorzugt **Bot-Passwörter** statt des Hauptkonto-Passworts (echte
  Bot-Passwörter bestehen nur aus Buchstaben/Ziffern, keine Sonderzeichen).
- **Jedes Passwort, das je in einem Chat oder Skript sichtbar war, widerrufen.**

## Entwicklung

```bash
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

Die netzwerkfreie Parsing-Logik liegt in `qs_parser.py` (Tests in
`tests/test_qs_parser.py`). CI: `.github/workflows/ci.yml`.

## Lizenz

MIT – siehe `LICENSE` (Namensfeld anpassen).