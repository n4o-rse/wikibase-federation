# Patch: Adopt-Tabelle mit den 93 schon angelegten Einträgen

Anlass: `idmap-chublets-wikibase.de.csv` und `state-...json` gingen lokal verloren. Aus dem Inventar des Wikis
(`--inventory`) sind alle 93 vorhandenen Einträge (P1–P83, Q1–Q10) über Label und Datentyp den CSV-Einträgen
zugeordnet; die Adopt-Tabelle ersetzt die alte mit 3 Zeilen. Der Lauf prüft vor dem Schreiben Label und Datentyp
(`url` im CSV entspricht `string` im Wiki), baut die `idmap` neu auf und legt nur die 85 fehlenden an.

## Einspielen
```
cd C:\git\wikibase-federation
tar -xf <Pfad>\chublets-adopt-3-patch.zip
git add -A && git commit -m "Chublets: adopt table for the 93 existing entities" && git push
```

## Prüfen
1. `python usecases\chublets\pipeline.py --probe` meldet die Adopt-Datei mit 93 Zeilen als OK.
2. Trockenlauf `python usecases\chublets\pipeline.py`: `adopted` 93, `created` 85, `claims written` 699, `write_calls` 0.
3. Echter Lauf `python usecases\chublets\pipeline.py --write` (bei Rate-Limit wartet er; bei `ABORT` später wiederholen).
   Danach `idmap-...csv` und `state-...json` sofort committen.
