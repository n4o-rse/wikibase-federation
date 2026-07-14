# Crosswalk — Ogham Federation Use Case (CIIC 81) — FROZEN

Subject: the Ogham stone **CIIC 81 / UCC Stone Corridor IV**, modelled as a *thin
federating hub* item (**Q5**) in `federated-objects.de`.

Reference frames: **Wikidata** for the generic layer, **CIDOC CRM** for the
domain-specific relations, and the **source Wikibases** (FactGrid, Fuzzy-SL,
Semantic Kompakkt, SquirrelBase, LinkedOgham) for the detail that stays
authoritative elsewhere.

**Modelling principle**
- Exact Wikidata property exists → reuse it. It is written via a **local
  property** and/or the **federated** `wd:P...` (see `PROPERTY_MODE`).
- Generic item values → **native Wikidata value federation**.
- Cross-Wikibase links → **per-source `external-id` + formatter URL** (Plan B),
  queried via SPARQL federation; upgradeable to native values later.
- **Local, new properties** only where our own frame applies (per-source IDs).
- Materialised values (coordinate, inscription) carry a **reference** to the
  source (also as external-id, since the url datatype is blocked here).

**Two switches (in `model.py`)** — same mechanism as the Software use case:
- `PROPERTY_MODE = "federated"` → predicate is `wd:P...` (needs Federated
  Properties); `"local"` → a local property (works on any Wikibase);
  `"local+federated"` → **both**, side by side, for the comparison. Each local
  equivalent records its Wikidata property via a string `equivalent Wikidata
  property` (P15). The cross-Wikibase links (#9–16) are always local.
- `USE_FEDERATED_VALUES` → item values as federated `wd:Q...` (default) or as
  external-id "Wikidata ID" literals (fully federation-free).

The live import used `PROPERTY_MODE = "local+federated"`.

**Why Plan B (external-id) and not url:** the **url datatype is blocked** on this
instance — url values fail to save (API + UI), while external-id/string/item
save fine. Each cross-Wikibase link is therefore an external-id plus a formatter
URL, which — once `formatterUrlProperty` is set — renders as a link and emits a
normalised IRI (`wdtn:`) for SPARQL federation.

---

## 1. Item terms (Q5)

| Term | Value |
|---|---|
| label (en) | Ogham Stone UCC Stone Corridor IV |
| alias (en) | CIIC 81 |
| description (en) | Ogham stone (CIIC 81 / UCC 4), UCC Stone Corridor, Cork |

---

## 2. Properties (live PIDs)

**(a) Local equivalents of the Wikidata predicates** — each carries `equivalent
Wikidata property = P<nn>`; in `local+federated` mode the fact is also written via
the `wd:P...` twin.

| Local property | PID | Datatype | Wikidata equiv |
|---|---|---|---|
| instance of | **P1** * | item | P31 |
| writing system | **P32** | item | P282 |
| location of discovery | **P33** | item | P189 |
| location | **P34** | item | P276 |
| collection | **P35** | item | P195 |
| coordinate location | **P36** | globe-coordinate | P625 |
| inscription | **P37** | monolingualtext | P1684 |
| equivalent Wikidata property | **P15** ** | string | — (meta) |

\* `instance of` reused the pre-existing local **P1** (label-conflict auto-resolve).
\*\* `equivalent Wikidata property` reused **P15**, created for the Software use case.

**(b) Cross-Wikibase links (Plan B)** — external-id + per-source formatter URL,
always local (no Wikidata equivalent).

| Local property | PID | Formatter URL |
|---|---|---|
| formatter URL | **P8** | (designates the ID formatter; needs `formatterUrlProperty`) |
| Wikidata ID | **P9** | http://www.wikidata.org/entity/$1 |
| FactGrid ID | **P10** | https://database.factgrid.de/entity/$1 |
| Fuzzy-SL ID | **P11** | https://fuzzy-sl.wikibase.cloud/entity/$1 |
| LinkedOgham ID | **P12** | http://lod.ogham.link/data/$1 |
| Semantic Kompakkt ID | **P13** | https://wikibase.semantic-kompakkt.de/entity/$1 |
| SquirrelBase ID | **P14** | https://squirrelbase.wikibase.cloud/entity/$1 |
| CIIC number | **P5** | (Macalister CIIC) |
| CISP id | **P6** | http://w3id.org/cispdb/stone/$1 |

(`has digital representation` P4 exists from an earlier iteration but is unused.)

---

## 3. Q5 — statements (all live)

**Wikidata-mapped (#1–8)** — in `local+federated` each is written twice: via the
local property and via the federated twin.

| # | Property | Local / Federated | Value | Reference |
|---|---|---|---|---|
| 1 | instance of | P1 / wd:P31 | wd:Q2016147 (Ogham stone) | — |
| 2 | writing system | P32 / wd:P282 | wd:Q184661 (Ogham) | — |
| 3 | location of discovery | P33 / wd:P189 | wd:Q69385525 (Garranes Site) | — |
| 4 | location of discovery | P33 / wd:P189 | wd:Q104295278 (Garranes townland) | — |
| 5 | location | P34 / wd:P276 | wd:Q69379477 (Stone Corridor UCC) | — |
| 6 | collection | P35 / wd:P195 | wd:Q1574185 (UCC) | — |
| 7 | coordinate location | P36 / wd:P625 | 51.893659, −8.492443 | P11 Fuzzy-SL = Q74 |
| 8 | inscription | P37 / wd:P1684 | "C[A]SSITT[A]S MAQI MUCOI CALLITI" @mul | P10 FactGrid = Q1000294 |

**Cross-Wikibase links (#9–16)** — external-id, always local.

| # | Property | Value |
|---|---|---|
| 9 | Wikidata ID (P9) | Q130529871 |
| 10 | FactGrid ID (P10) | Q1000294 |
| 11 | Fuzzy-SL ID (P11) | Q74 |
| 12 | LinkedOgham ID (P12) | Y50000081 |
| 13 | Semantic Kompakkt ID (P13) | Q1247 |
| 14 | SquirrelBase ID (P14) | Q48 |
| 15 | CIIC number (P5) | 81 |
| 16 | CISP id (P6) | gares_1 |

Findspot coordinate (Garranes ~51.8166 / −8.7659) is a `wd:P625` qualifier on #3,
not a second primary coordinate.

---

## 4. Stays authoritative elsewhere (not copied)

| Detail | Source of truth | Reached via |
|---|---|---|
| Rich spatial info (fuzzy locations, 2nd point) | Fuzzy-SL Q74 | P11 |
| Related persons (CASSITTAS, CALLITI) | FactGrid Q1000294 | P10 |
| 3D model + annotations | Semantic Kompakkt Q1247 | P13 |
| FDO + Zenodo DOI | SquirrelBase Q48 | P14 |

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

`fotn:` = this instance's normalised-value prefix. Requires FactGrid on the
query-service allowlist.

---

## 6. Instance-config findings (reported to WMDE devs)

1. **url datatype blocked** — url values fail to save (API + UI); external-id /
   string / item save fine. Bridged via external-id + formatter.
2. **Federated items show "(Deleted Item)"** — federated Wikidata item values
   render unresolved via the API until registered once via the UI (alpha gap).
3. **`formatterUrlProperty` not set** — set it (e.g. to P8) so external-ids
   render as links and emit the `wdtn:` IRI the query above needs.
4. **`internal_api_error_TypeError`** — transient PHP TypeError on rapid
   `wbcreateclaim` / `wbgetentities`; mitigated client-side by retry + throttle.

---

## 7. Reproduce

`python main.py` with `[job] job_dir = usecases/ogham` and `[run] pipeline =
true`: ensure hub item (Q5) → ensure local properties (P1 reused, P15 reused,
P32–P37 + the external-id set) + formatters + equivalence mappings → build
input.qs → import → apply references. Idempotent, dry-run-safe, retries transient
errors. Source of truth: `usecases/ogham/model.py`. Flip `PROPERTY_MODE = "local"`
or `"federated"` for the other two variants.