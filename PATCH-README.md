# Patch wikibase-federation 1.2.2: Rate-Limit-Behandlung und ruff

Anlass: Der erste echte Lauf (`--write`) legte 90 Einträge an und wurde dann vom Wiki wegen
"Anti-Missbrauchs-Maßnahme" abgewiesen (85 Einträge `FAILED`, 379 Aussagen davon abhängig). Das war kein
Datentyp-Problem. Zudem schlug in der Action `ruff` an (29 × E501, Zeilenlänge).

## Inhalt
- `usecases/chublets/push.py`: bei Rate-Limit warten und wiederholen (`rate_limit_wait`, `rate_limit_retries`),
  danach `PushAbort` mit Hinweis; idmap und state sind schon gespeichert, ein neuer Lauf macht weiter.
- `usecases/chublets/pipeline.py`: liest die zwei neuen Einstellungen, `throttle_seconds` Standard 1,
  bei Abbruch Zwischenstand ausgeben.
- `pyproject.toml`: E501 für die Chublets-Dateien ignoriert; Version 1.2.2 (auch `wbqs/__init__.py`).
- `tests/test_chublets_push.py`: 3 neue Tests (69 insgesamt). `config.example.ini`, `CHANGELOG.md`, README.

## Einspielen
```
cd C:\git\wikibase-federation
tar -xf <Pfad>\chublets-ratelimit-patch.zip
git add -A && git commit -m "Chublets push: wait on rate limit, lint (1.2.2)" && git push
```
(ZIP vorher in den Repo-Ordner entpacken, die Dateien überschreiben die alten.)

## Prüfen
1. `python -m pytest -q` meldet `69 passed`; `ruff check .` meldet `All checks passed!` (falls `ruff` fehlt: `pip install --user ruff`).
2. Die Action ist grün.
3. Erneut `python usecases\chublets\pipeline.py` (Trockenlauf): `created` ist jetzt um die schon angelegten 90 kleiner,
   `write_calls` ist 0. Die Dateien `idmap-chublets-wikibase.de.csv` und `state-...json` müssen vorher noch im Ordner liegen.
4. Echter Lauf: `python usecases\chublets\pipeline.py --write`. Bei Rate-Limit erscheint
   `Rate limit hit; waiting 60s`. Endet der Lauf mit `ABORT`, später denselben Befehl wiederholen.
5. Besser auf Dauer: Konto `Fthierygeo` in Special:UserRights der Wikibase in die Gruppe `bot` setzen
   und in `config.ini` `mark_bot = true` – dann entfällt das Limit.
