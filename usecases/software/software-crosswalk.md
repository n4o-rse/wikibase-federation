# Crosswalk — Software Federation Use Case (CodeMeta) — FROZEN

Subjects: two real research-software items, modelled in `federated-objects.de`:
- **Q6** — SPARQLing Unicorn QGIS Plugin (Wikidata Q74005133)
- **Q7** — Academic Meta Tool / AMT (Wikidata Q74003194)

Reference frames: **Wikidata** (Q7397 software) for the shared layer, **CodeMeta**
for the software-specific fields Wikidata does not cover.

**Modelling principle — works with *and* without federated properties.**
- Every predicate is a **local property**; the model therefore runs on any
  Wikibase, even without the Federated Properties feature.
- Each local property records its Wikidata equivalent via a local string property
  `equivalent Wikidata property` (P15) — we use a string, not `equivalent
  property (P1628)`, because P1628 is url datatype and url is blocked here.
- Item values are **federated Wikidata items** (wd:Q...) — that is *value*
  federation, a separate feature and the actual showcase.
- url-typed CodeMeta fields (codeRepository, url, readme, CI) are modelled as
  **string** because the url datatype is blocked on this instance.

**Two switches (in `model.py`)**
- `PROPERTY_MODE = "local"` → only local predicates (no Federated Properties).
- `PROPERTY_MODE = "local+federated"` → each Wikidata-mappable statement is
  written **twice** (local + `wd:P...`) on the same item, for a side-by-side
  "with vs. without federation" comparison. url-typed federated duplicates are
  skipped (they would hit the url block).
- `USE_FEDERATED_VALUES = True/False` → item values as federated wd:Q... or, if
  false, as external-id "Wikidata ID" literals (fully federation-free).

The live import used `PROPERTY_MODE = "local+federated"`, `USE_FEDERATED_VALUES = True`.

---

## 1. Properties (live PIDs)

| # | Local property | PID | Datatype | CodeMeta term | Wikidata equiv | Bucket |
|---|---|---|---|---|---|---|
| — | equivalent Wikidata property | **P15** | string | — | — | meta (mapping) |
| 1 | instance of | **P1** * | item | @type | P31 | Wikidata-mapped |
| 2 | developer | **P18** | item | author | P178 | Wikidata-mapped |
| 3 | programmed in | **P19** | item | programmingLanguage | P277 | Wikidata-mapped |
| 4 | copyright license | **P20** | item | license | P275 | Wikidata-mapped |
| 5 | software version | **P21** | string | softwareVersion | P348 | Wikidata-mapped |
| 6 | DOI | **P22** | external-id | identifier | P356 | Wikidata-mapped |
| 7 | source code repository | **P23** | string ** | codeRepository | P1324 | Wikidata-mapped |
| 8 | official website | **P24** | string ** | url | P856 | Wikidata-mapped |
| 9 | development status | **P25** | string | developmentStatus | — | CodeMeta-only |
| 10 | continuous integration | **P26** | string | continuousIntegration | — | CodeMeta-only |
| 11 | README URL | **P27** | string | readme | — | CodeMeta-only |
| 12 | build instructions | **P28** | string | buildInstructions | — | CodeMeta-only |
| 13 | code sample type | **P29** | string | codeSampleType | — | CodeMeta-only |

\* `instance of` reused the pre-existing local property **P1** (label-conflict
auto-resolve), rather than creating a duplicate.
\*\* url datatype in Wikidata; stored as `string` because url is blocked here.
The federated duplicate (`wd:P1324` / `wd:P856`) is therefore skipped.

Each Wikidata-mapped property carries `equivalent Wikidata property = P<nn>` on
the property itself (e.g. Property:P18 → "P178"), so the local↔Wikidata mapping
is machine-readable on the instance.

---

## 2. Q6 — SPARQLing Unicorn QGIS Plugin

Label: "SPARQLing Unicorn QGIS Plugin".
Description: "Plugin to add a layer in QGIS from Linked Data SPARQL endpoints."

| Local property | Value | Federated twin |
|---|---|---|
| instance of (P1) | wd:Q7397 (software) | wd:P31 |
| developer (P18) | wd:Q66606154, wd:Q67624599, wd:Q73901970 | wd:P178 |
| programmed in (P19) | wd:Q28865 (Python) | wd:P277 |
| software version (P21) | 0.17.4 | wd:P348 |
| DOI (P22) | 10.5281/ZENODO.13828632 | wd:P356 |
| source code repository (P23) | https://github.com/sparqlunicorn/sparqlunicornGoesGIS | — (url blocked) |
| official website (P24) | https://plugins.qgis.org/plugins/sparqlunicorn/ | — (url blocked) |
| development status (P25) | active | — (CodeMeta-only) |
| README URL (P27) | https://github.com/sparqlunicorn/sparqlunicornGoesGIS#readme | — |
| continuous integration (P26) | https://github.com/sparqlunicorn/sparqlunicornGoesGIS/actions | — |
| code sample type (P29) | QGIS plugin | — |

CodeMeta-only values (development status, README, CI, code sample type) are
illustrative; the properties are the point, the values can be curated.

---

## 3. Q7 — Academic Meta Tool (AMT)

Label: "Academic Meta Tool" (alias "AMT").
Description: "ontology and webapp for modelling vagueness in graphs including reasoning".

| Local property | Value | Federated twin |
|---|---|---|
| instance of (P1) | wd:Q7397 (software) | wd:P31 |
| developer (P18) | wd:Q66606154, wd:Q47213994 (mainzed) | wd:P178 |
| copyright license (P20) | wd:Q334661 | wd:P275 |
| source code repository (P23) | https://github.com/search?q=topic%3Aacademicmetatool+org%3Amainzed+fork%3Atrue | — (url blocked) |
| official website (P24) | http://academic-meta-tool.xyz | — (url blocked) |
| development status (P25) | active | — |
| README URL (P27) | http://academic-meta-tool.xyz/ontology/ | — |
| build instructions (P28) | http://academic-meta-tool.xyz | — |
| code sample type (P29) | web application | — |

The two subjects deliberately carry different fields (SU has version/DOI/language;
AMT has license) — showing the model handles partial coverage.

---

## 4. What this demonstrates

- **Fall 2 (Wikidata ontology reuse), in two flavours simultaneously.** In
  `local+federated` mode each Wikidata-mappable fact appears twice on the item:
  once via a local property (portable, works anywhere) and once via `wd:P...`
  (needs Federated Properties). The local property is tied to Wikidata by the
  `equivalent Wikidata property` statement. This is the direct "with vs. without
  federation" comparison, on the property axis.
- **Own reference frame (CodeMeta).** The 5 CodeMeta-only properties (P25–P29)
  are the software equivalent of Ogham's CIDOC-CRM-specific local properties:
  domain semantics that Wikidata does not express.
- **Total live:** 34 statements across Q6 (22) and Q7 (16 after url-dup skips).

---

## 5. Instance-config findings (reported to WMDE devs)

1. **url datatype blocked** — url values fail to save (API + UI). All url-typed
   CodeMeta fields are modelled as string here.
2. **Federated items show "(Deleted Item)"** — federated Wikidata item *values*
   render unresolved via the API (registration gap in the alpha). Registering an
   item once via the UI resolves it.
3. **`formatterUrlProperty` not set** — external-ids (DOI) don't render as links
   and emit no `wdtn:` IRI until the instance designates the formatter property.
4. **`internal_api_error_TypeError`** — transient PHP TypeError on rapid
   `wbcreateclaim` sequences, even for valid federated item values. Mitigated
   client-side by retry + throttle; worth a server-side look.

---

## 6. Reproduce

`python main.py` with `[job] job_dir = usecases/software` and `[run] pipeline =
true`: ensure items (Q6, Q7) → ensure local properties (P15, P18–P29; P1 reused)
+ equivalence mappings → build input.qs → import. Idempotent, dry-run-safe,
retries transient errors. Source of truth: `usecases/software/model.py`.
Flip `PROPERTY_MODE = "local"` for a federation-free property run.
