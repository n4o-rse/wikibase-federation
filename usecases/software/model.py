#!/usr/bin/env python3
"""
Frozen data model for the Software federation use case (CodeMeta crosswalk).

Design (differs from Ogham on purpose):
- NO federated properties. Every predicate is a LOCAL property, so the model
  works on any Wikibase even without the Federated Properties feature. Each local
  property records its Wikidata equivalent (wd_equiv) and CodeMeta term for the
  crosswalk (and, later, an 'equivalent property' statement).
- Item values MAY still be federated Wikidata items (wd:Q...) — that is *value*
  federation (the Ontology Federation alpha), a separate feature and the actual
  showcase. Combination on each such statement: local property + federated value.
- url-typed CodeMeta fields (codeRepository, url, readme, CI) are modelled as
  `string` because the url datatype is blocked on this instance; the URL is
  stored as literal text. Switch to `url` once the instance unblocks it.
- Two real subjects, each created as a local item.

Reference frames: Wikidata (Q7397 software) for the shared layer, CodeMeta for
the software-specific fields that Wikidata does not cover.

Plain data; no network here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WD = "http://www.wikidata.org/entity/"

# Whether Wikidata-concept item values are written as federated values (wd:Q...)
# or, if False, as external-id "Wikidata ID" literals (fully federation-free).
USE_FEDERATED_VALUES = True

# How predicates are written for the 8 fields that have a Wikidata property:
#   "local"           -> only the local property (works without Federated Properties)
#   "local+federated" -> both the local property AND the federated wd:P... on the
#                        same item, so the two paths can be compared side by side.
# The 5 CodeMeta-only fields are always local (no Wikidata equivalent).
PROPERTY_MODE = "local+federated"

# Local string property that records each local property's Wikidata equivalent
# (we use a string "Wikidata property ID" because equivalent property (P1628) is
# url datatype and url is blocked on this instance).
EQUIV_PROPERTY = {
    "key": "equiv_wikidata_property",
    "label": "equivalent Wikidata property",
    "datatype": "string",
    "description": "the Wikidata property this local property is equivalent to (e.g. P31)",
}

# --- Local properties (predicates). No federated properties are used. ---------
# 8 with a Wikidata equivalent + 5 CodeMeta-only (no Wikidata property).
LOCAL_PROPERTIES = [
    # --- with a Wikidata equivalent (wd_equiv/wd_datatype are documentation) ---
    {"key": "instance_of", "label": "instance of", "datatype": "wikibase-item",
     "wd_equiv": "P31", "wd_datatype": "wikibase-item", "codemeta": "@type",
     "description": "type to which this software belongs"},
    {"key": "developer", "label": "developer", "datatype": "wikibase-item",
     "wd_equiv": "P178", "wd_datatype": "wikibase-item", "codemeta": "author",
     "description": "organization or person that developed the software"},
    {"key": "programmed_in", "label": "programmed in", "datatype": "wikibase-item",
     "wd_equiv": "P277", "wd_datatype": "wikibase-item", "codemeta": "programmingLanguage",
     "description": "the programming language(s) the software is developed in"},
    {"key": "license", "label": "copyright license", "datatype": "wikibase-item",
     "wd_equiv": "P275", "wd_datatype": "wikibase-item", "codemeta": "license",
     "description": "license under which this software is released"},
    {"key": "software_version", "label": "software version", "datatype": "string",
     "wd_equiv": "P348", "wd_datatype": "string", "codemeta": "softwareVersion",
     "description": "version identifier of the software"},
    {"key": "doi", "label": "DOI", "datatype": "external-id",
     "wd_equiv": "P356", "wd_datatype": "external-id", "codemeta": "identifier",
     "description": "Digital Object Identifier for the software"},
    # url datatype in Wikidata -> modelled as string here (url is blocked); the
    # federated duplicate is skipped (it would hit the same url block).
    {"key": "source_code_repository", "label": "source code repository", "datatype": "string",
     "wd_equiv": "P1324", "wd_datatype": "url", "codemeta": "codeRepository",
     "description": "public source code repository (string: url datatype is blocked here)"},
    {"key": "official_website", "label": "official website", "datatype": "string",
     "wd_equiv": "P856", "wd_datatype": "url", "codemeta": "url",
     "description": "official website (string: url datatype is blocked here)"},
    # --- CodeMeta-only: no Wikidata equivalent -> own reference frame ---
    {"key": "development_status", "label": "development status", "datatype": "string",
     "codemeta": "developmentStatus",
     "description": "development status per repostatus.org (e.g. active, inactive)"},
    {"key": "continuous_integration", "label": "continuous integration", "datatype": "string",
     "codemeta": "continuousIntegration",
     "description": "link to the continuous integration service"},
    {"key": "readme", "label": "README URL", "datatype": "string",
     "codemeta": "readme",
     "description": "link to the software README file"},
    {"key": "build_instructions", "label": "build instructions", "datatype": "string",
     "codemeta": "buildInstructions",
     "description": "link to installation / build instructions"},
    {"key": "code_sample_type", "label": "code sample type", "datatype": "string",
     "codemeta": "codeSampleType",
     "description": "kind of code artefact (full solution, script, plugin, web app, ...)"},
]


@dataclass
class Statement:
    """One statement on a subject item.

    prop:       local property key (e.g. "instance_of").
    value_kind: item | string | external_id
    value:      item -> Wikidata QID string ("Q7397"); else the literal value.
    note:       free text.
    """

    prop: str
    value_kind: str
    value: object
    note: str = ""


@dataclass
class Item:
    key: str
    terms: dict
    statements: list = field(default_factory=list)


# --- Subjects -----------------------------------------------------------------
# Item values reference Wikidata QIDs; real values taken from the Wikidata items
# (Q74005133, Q74003194). CodeMeta-only values marked (illustrative) are
# conventional/derived examples to demonstrate the own-frame fields.
ITEMS = [
    Item(
        key="sparqlunicorn",
        terms={
            "labels": {"en": "SPARQLing Unicorn QGIS Plugin"},
            "descriptions": {"en": "Plugin to add a layer in QGIS from Linked Data SPARQL endpoints."},
            "aliases": {},
        },
        statements=[
            Statement("instance_of", "item", "Q7397", "software"),
            Statement("developer", "item", "Q66606154"),
            Statement("developer", "item", "Q67624599"),
            Statement("developer", "item", "Q73901970"),
            Statement("programmed_in", "item", "Q28865", "Python"),
            Statement("software_version", "string", "0.17.4", "latest / preferred"),
            Statement("doi", "external_id", "10.5281/ZENODO.13828632"),
            Statement("source_code_repository", "string",
                      "https://github.com/sparqlunicorn/sparqlunicornGoesGIS"),
            Statement("official_website", "string",
                      "https://plugins.qgis.org/plugins/sparqlunicorn/"),
            # CodeMeta-only (illustrative)
            Statement("development_status", "string", "active", "illustrative (repostatus.org)"),
            Statement("readme", "string",
                      "https://github.com/sparqlunicorn/sparqlunicornGoesGIS#readme", "illustrative"),
            Statement("continuous_integration", "string",
                      "https://github.com/sparqlunicorn/sparqlunicornGoesGIS/actions", "illustrative"),
            Statement("code_sample_type", "string", "QGIS plugin", "illustrative"),
        ],
    ),
    Item(
        key="amt",
        terms={
            "labels": {"en": "Academic Meta Tool"},
            "descriptions": {
                "en": "ontology and webapp for modelling vagueness in graphs including reasoning",
            },
            "aliases": {"en": ["AMT"]},
        },
        statements=[
            Statement("instance_of", "item", "Q7397", "software"),
            Statement("developer", "item", "Q66606154"),
            Statement("developer", "item", "Q47213994"),
            Statement("license", "item", "Q334661", "a free license (from Wikidata)"),
            Statement("source_code_repository", "string",
                      "https://github.com/search?q=topic%3Aacademicmetatool+org%3Amainzed+fork%3Atrue"),
            Statement("official_website", "string", "http://academic-meta-tool.xyz"),
            # CodeMeta-only (illustrative)
            Statement("development_status", "string", "active", "illustrative (repostatus.org)"),
            Statement("readme", "string", "http://academic-meta-tool.xyz/ontology/", "illustrative"),
            Statement("build_instructions", "string",
                      "http://academic-meta-tool.xyz", "illustrative"),
            Statement("code_sample_type", "string", "web application", "illustrative"),
        ],
    ),
]

SUPPORTED_VALUE_KINDS_TODAY = {"item", "string", "external_id"}
