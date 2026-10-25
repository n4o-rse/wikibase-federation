# Patch wikibase-federation 1.2.3: Texte über 250 Zeichen kürzen

Anlass: Im Lauf mit 200 Items lehnte das Wiki drei Items ab (CSV Q150, Q281, Q289): „Description must be no more than 250
characters long“. Insgesamt sind 22 der 796 open-archaeo-Items betroffen (längste Beschreibung 642 Zeichen).

## Inhalt
- `usecases/chublets/push.py`: `shorten` kürzt Bezeichnung, Beschreibung und Aliasse auf höchstens 250 Zeichen, an einer
  Wortgrenze, mit „…“ am Ende; der Bericht führt sie unter `shortened`. Die CSV bleibt unverändert.
- `usecases/chublets/pipeline.py`: meldet die Zahl der gekürzten Texte.
- `tests/test_chublets_push.py`: 2 neue Tests (71 insgesamt); die Attrappe des Wikis lehnt Texte über 250 Zeichen ab.
- `CHANGELOG.md`, `README.md` des Usecase, Version 1.2.3 in `pyproject.toml` und `wbqs/__init__.py`.

## Einspielen
```
cd C:\git\wikibase-federation
tar -xf <Pfad>\chublets-shorten-patch.zip
git add -A && git commit -m "Chublets push: shorten texts to 250 characters (1.2.3)" && git push
```
(`PATCH-README.md` dabei nicht einchecken: `git reset PATCH-README.md` vor dem Commit, oder löschen.)

## Prüfen
1. `python -m pytest -q` meldet `71 passed`; `ruff check .` meldet `All checks passed!`.
2. `python usecases\chublets\pipeline.py --phase items --origin open-archaeo --limit 200` (Trockenlauf): `created` 3,
   `skipped` 197, und die Zeile „shortened to 250 characters: 3“.
3. Echter Lauf mit `--write`: `created` 3, `failed` 0. Danach `idmap` und `state` committen.
