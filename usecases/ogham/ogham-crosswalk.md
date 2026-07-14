# Crosswalk — Ogham Federation Use Case (CIIC 81) — FROZEN (Plan B)

Subject: the Ogham stone **CIIC 81 / UCC Stone Corridor #4**, modelled as a *thin
federating hub* item (**Q5**) in `federated-objects.de`.

**Modelling principle**
- Exact Wikidata property exists → **federated Wikidata property** (Fall 2).
- Generic item values → **native Wikidata federation** (works today).
- Cross-Wikibase links → **per-source `external-id` + formatter URL** (Plan B),
  queried via SPARQL federation; upgradeable to native values later.
- **Local, new properties only** where our own CIDOC CRM frame applies.
- Materialised values (coordinate, inscription) carry a **reference** to the
  source (also as external-id, since url datatype is blocked here).

**Why Plan B (external-id) and not url:** on this instance the **url datatype is
blocked** — url values fail to save via both API and UI (`failed-save`), while
external-id/string/item save fine. Each cross-Wikibase link is therefore an
external-id (`Q1000294`) plus a formatter URL (`https://database.factgrid.de/entity/$1`),
which — once the instance's `formatterUrlProperty` is set — renders as a link and
emits a normalised IRI node (`wdtn:`) in RDF, exactly what SPARQL federation needs.

---

## 1. Item terms (Q5)

| Term | Value |
|---|---|
| label (en) | Ogham Stone UCC Stone Corridor IV |
| alias (en) | CIIC 81 |
| description (en) | Ogham stone (CIIC 81 / UCC 4), UCC Stone Corridor, Cork |

---

## 2. Properties

Pre-existing local: P1 instance of, P2 place of birth, P3 subclass of.
Federated Wikidata properties are used directly (proven via the wd:P5572 test).

| Property | Source / PID | Datatype | Role |
|---|---|---|---|
| instance of | wd:P31 | item | classification (Ogham stone) |
| writing system | wd:P282 | item | script = Ogham |
| location of discovery | wd:P189 | item | findspot (Garranes) |
| location | wd:P276 | item | current location = Stone Corridor |
| collection | wd:P195 | item | holding institution = UCC |
| coordinate location | wd:P625 | globe-coordinate | current-location coordinate |
| inscription | wd:P1684 | monolingual (mul) | materialised from FactGrid + reference |
| formatter URL | **P8** (local) | string | designates the ID formatter (needs `formatterUrlProperty`) |
| Wikidata ID | **P9** (local) | external-id | same object in Wikidata |
| FactGrid ID | **P10** (local) | external-id | same object in FactGrid |
| Fuzzy-SL ID | **P11** (local) | external-id | same object in Fuzzy-SL |
| LinkedOgham ID | **P12** (local) | external-id | same object in LinkedOgham |
| Semantic Kompakkt ID | **P13** (local) | external-id | 3D representation (CIDOC P138i) |
| SquirrelBase ID | **P14** (local) | external-id | FDO / 3D (CIDOC P138i) |
| CIIC number | **P5** (local) | external-id | Macalister CIIC |
| CISP id | **P6** (local) | external-id | CISP database |

Each ID property carries a formatter URL (set via P8), e.g. `…/entity/$1`.

---

## 3. Q5 — statements (all live, 16/16)

| # | Property | Value | Reference |
|---|---|---|---|
| 1 | wd:P31 instance of | wd:Q2016147 (Ogham stone) | — |
| 2 | wd:P282 writing system | wd:Q184661 (Ogham) | — |
| 3 | wd:P189 location of discovery | wd:Q69385525 (Garranes Site) + findspot coord (qualifier) | — |
| 4 | wd:P189 location of discovery | wd:Q104295278 (Garranes townland) | — |
| 5 | wd:P276 location | wd:Q69379477 (Stone Corridor UCC) | — |
| 6 | wd:P195 collection | wd:Q1574185 (UCC) | — |
| 7 | wd:P625 coordinate | 51.893659, −8.492443 | P11 Fuzzy-SL = Q74 |
| 8 | wd:P1684 inscription | "C[A]SSITT[A]S MAQI MUCOI CALLITI" @mul | P10 FactGrid = Q1000294 |
| 9 | P9 Wikidata ID | Q130529871 | — |
| 10 | P10 FactGrid ID | Q1000294 | — |
| 11 | P11 Fuzzy-SL ID | Q74 | — |
| 12 | P12 LinkedOgham ID | Y50000081 | — |
| 13 | P13 Semantic Kompakkt ID | Q1247 | — |
| 14 | P14 SquirrelBase ID | Q48 | — |
| 15 | P5 CIIC number | 81 | — |
| 16 | P6 CISP id | gares_1 | — |

Findspot coordinate (Garranes ~51.8166 / −8.7659) is a `wd:P625` qualifier on #3,
not a second primary coordinate.

---

## 4. Stays authoritative elsewhere (not copied)

| Detail | Source of truth | Reached via |
|---|---|---|
| Rich spatial info (fuzzy locations, 2nd point) | Fuzzy-SL Q74 | P11 |
| Related persons (CASSITTAS, CALLITI) | FactGrid Q1000294 | P10 |
| 3D model + annotations | Semantic Kompakkt Q1247 | P13 |
| FDO + Zenodo DOI (10.5281/zenodo.18724635) | SquirrelBase Q48 | P14 |

Inscription (#8) is materialised *with a reference* to FactGrid; FactGrid stays
the single source of truth.

---

## 5. Proof query (inscription live from FactGrid via the normalised IRI)

After `formatterUrlProperty` is set, the FactGrid ID emits a `wdtn:` IRI node:

```sparql
SELECT ?inscription WHERE {
  fo:Q5 fotn:P10 ?fgItem .                     # normalised IRI of the FactGrid ID
  SERVICE <https://database.factgrid.de/sparql> {
    ?fgItem fgt:P1219 ?inscription .           # inscription text in FactGrid
  }
}
```

`fotn:` = this instance's normalised-value prefix (…/prop/direct-normalized/).
Run on the instance query service if FactGrid is allowlisted, else via
`sparql.dblp.org`.

---

## 6. Open instance-config items (reported to WMDE devs)

1. **url datatype blocked** — url values fail to save (API + UI); external-id /
   string / item save fine. Needs a look at SpamBlacklist / AbuseFilter /
   `$wgUrlProtocols` / url validation.
2. **Federated items show "(Deleted Item)"** — newly referenced Wikidata items
   render unresolved via the API path; the alpha's API representation of
   federated items is not implemented yet. Registering each item once via the UI
   resolves it.
3. **`formatterUrlProperty` not set** — set
   `$wgWBRepoSettings['formatterUrlProperty'] = 'P8'` (+ rebuildPropertyInfo.php),
   or map P8 to P1630 on wikibase.cloud, so external-ids render as links and emit
   the `wdtn:` IRI needed by the query above.

---

## 7. Reproduce

`python main.py` (pipeline): ensure Q5 → ensure P5/P6/P8–P14 + formatters →
build input.qs → import 16 statements → apply references. Idempotent and
dry-run-safe. Source of truth: `usecases/ogham/model.py`.
