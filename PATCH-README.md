# Patch wikibase-federation 1.2.4 (nur Dokumentation)

## Inhalt
- `usecases/chublets/README.md`: Ergebnis des Push, föderierte Werte bestätigt, Idmap wird von wikibase-static veröffentlicht, kein `bot`-Recht
- `CHANGELOG.md`, `pyproject.toml`, `wbqs/__init__.py` (Version 1.2.4)

## Einspielen (Windows cmd, in `C:\git\wikibase-federation`)
    tar -xf <pfad>\federation-closing-patch.zip
    python -m pytest -q
    ruff check .
    git status

## Prüfen
- 71 passed, ruff ohne Fehler; `git status` zeigt `PATCH-README.md` und die vier Dateien oben

## Commit
    git add -A
    git commit -m "1.2.4: Chublets push abgeschlossen, Dokumentation"
    git push
