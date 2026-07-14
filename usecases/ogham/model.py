#!/usr/bin/env python3
"""
Frozen data model for the Ogham federation use case (CIIC 81).

This module is the single machine-readable source of truth. Both the QS builder
(build_qs.py) and the property-creation step read from here, so the human-facing
crosswalk (MODEL.md) and the generated artefacts never drift apart.

Nothing here touches the network; it is plain data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

WD = "http://www.wikidata.org/entity/"

# The local hub item that receives the statements.
HUB_ITEM = "Q5"

# How the 7 predicates that have a Wikidata property are written:
#   "federated"       -> only wd:P...        (needs Federated Properties; original)
#   "local"           -> only local property (works on any Wikibase)
#   "local+federated" -> both, side by side  (the comparison)
# The cross-Wikibase links (#9-16) are always local (no Wikidata equivalent).
PROPERTY_MODE = "local+federated"

# Local string property recording each local property's Wikidata equivalent
# (string, because equivalent property (P1628) is url datatype and url is blocked).
EQUIV_PROPERTY = {
    "key": "equiv_wikidata_property",
    "label": "equivalent Wikidata property",
    "datatype": "string",
    "description": "the Wikidata property this local property is equivalent to (e.g. P31)",
}

# Item terms (set via wbeditentity, not as statements).
TERMS = {
    "labels": {"en": "Ogham Stone UCC Stone Corridor IV"},
    "aliases": {"en": ["CIIC 81"]},
    "descriptions": {"en": "Ogham stone (CIIC 81 / UCC 4), UCC Stone Corridor, Cork"},
}

# Local properties to create. Two groups:
#  (a) local equivalents of the Wikidata predicates (wd_equiv/wd_datatype set);
#  (b) the Plan-B cross-Wikibase links (external-id + formatter URL).
LOCAL_PROPERTIES = [
    # (a) local equivalents of the federated Wikidata predicates
    {"key": "instance_of", "label": "instance of", "datatype": "wikibase-item",
     "wd_equiv": "P31", "wd_datatype": "wikibase-item",
     "description": "type to which this object belongs"},
    {"key": "writing_system", "label": "writing system", "datatype": "wikibase-item",
     "wd_equiv": "P282", "wd_datatype": "wikibase-item",
     "description": "writing system used for the inscription"},
    {"key": "location_of_discovery", "label": "location of discovery", "datatype": "wikibase-item",
     "wd_equiv": "P189", "wd_datatype": "wikibase-item",
     "description": "place where the object was found"},
    {"key": "location", "label": "location", "datatype": "wikibase-item",
     "wd_equiv": "P276", "wd_datatype": "wikibase-item",
     "description": "current physical location of the object"},
    {"key": "collection", "label": "collection", "datatype": "wikibase-item",
     "wd_equiv": "P195", "wd_datatype": "wikibase-item",
     "description": "holding institution / collection"},
    {"key": "coordinate_location", "label": "coordinate location", "datatype": "globe-coordinate",
     "wd_equiv": "P625", "wd_datatype": "globe-coordinate",
     "description": "geographic coordinates of the object"},
    {"key": "inscription", "label": "inscription", "datatype": "monolingualtext",
     "wd_equiv": "P1684", "wd_datatype": "monolingualtext",
     "description": "text of the inscription"},
    # (b) Plan-B cross-Wikibase links: external-id + per-source formatter URL
    {
        "key": "formatter_url",
        "label": "formatter URL",
        "description": "web page URL template; $1 is replaced by the external identifier",
        "datatype": "string",
    },
    {
        "key": "wikidata_id",
        "label": "Wikidata ID",
        "description": "the same object's item in Wikidata (skos:exactMatch)",
        "datatype": "external-id",
        "formatter": "http://www.wikidata.org/entity/$1",
    },
    {
        "key": "factgrid_id",
        "label": "FactGrid ID",
        "description": "the same object's item in FactGrid (skos:exactMatch)",
        "datatype": "external-id",
        "formatter": "https://database.factgrid.de/entity/$1",
    },
    {
        "key": "fuzzysl_id",
        "label": "Fuzzy-SL ID",
        "description": "the same object's item in Fuzzy Spatial Locations (skos:exactMatch)",
        "datatype": "external-id",
        "formatter": "https://fuzzy-sl.wikibase.cloud/entity/$1",
    },
    {
        "key": "linkedogham_id",
        "label": "LinkedOgham ID",
        "description": "the same object's record in LinkedOgham (skos:exactMatch)",
        "datatype": "external-id",
        "formatter": "http://lod.ogham.link/data/$1",
    },
    {
        "key": "semantickompakkt_id",
        "label": "Semantic Kompakkt ID",
        "description": "3D representation of this object in Semantic Kompakkt (CIDOC P138i)",
        "datatype": "external-id",
        "formatter": "https://wikibase.semantic-kompakkt.de/entity/$1",
    },
    {
        "key": "squirrelbase_id",
        "label": "SquirrelBase ID",
        "description": "FAIR Digital Object / 3D data for this object in SquirrelBase (CIDOC P138i)",
        "datatype": "external-id",
        "formatter": "https://squirrelbase.wikibase.cloud/entity/$1",
    },
    {
        "key": "ciic_number",
        "label": "CIIC number",
        "description": "identifier in Macalister's Corpus Inscriptionum Insularum Celticarum",
        "datatype": "external-id",
    },
    {
        "key": "cisp_id",
        "label": "CISP id",
        "description": "identifier in the Celtic Inscribed Stones Project database",
        "datatype": "external-id",
        "formatter": "http://w3id.org/cispdb/stone/$1",
    },
]


@dataclass
class Statement:
    """One planned statement on the hub item.

    prop:        the property token as written to QS. Either a federated Wikidata
                 property ("wd:P31") or a local property key ("@has_digital_representation")
                 to be resolved to a real PID after property creation.
    value_kind:  item | url | monolingual | coordinate | external_id
    value:       for item -> full entity URI; url -> IRI; external_id -> the id
                 string; monolingual -> (text, lang); coordinate -> (lat, lon)
    references:  list of (prop_token, value_kind, value) snaks giving provenance.
                 We use external-id snaks (e.g. @factgrid_id) because the url
                 datatype (wd:P854 reference URL) is blocked on this instance.
    qualifiers:  optional list of (prop, value_kind, value)
    """

    n: int
    prop: str
    value_kind: str
    value: object
    label: str = ""
    references: list = field(default_factory=list)
    qualifiers: list = field(default_factory=list)
    note: str = ""


# The frozen statement plan (section 3 of the crosswalk).
STATEMENTS = [
    Statement(1, "wd:P31", "item", f"{WD}Q2016147", "instance of: Ogham stone"),
    Statement(2, "wd:P282", "item", f"{WD}Q184661", "writing system: Ogham"),
    Statement(3, "wd:P189", "item", f"{WD}Q69385525", "findspot: Garranes (Ogham Site)",
              qualifiers=[("wd:P625", "coordinate", (51.81655, -8.765869))]),
    Statement(4, "wd:P189", "item", f"{WD}Q104295278", "findspot: Garranes (townland)"),
    Statement(5, "wd:P276", "item", f"{WD}Q69379477", "location: Stone Corridor UCC"),
    Statement(6, "wd:P195", "item", f"{WD}Q1574185", "collection: University College Cork"),
    Statement(7, "wd:P625", "coordinate", (51.893659, -8.492443), "coordinate (UCC, primary)",
              references=[("@fuzzysl_id", "external_id", "Q74")]),
    Statement(8, "wd:P1684", "monolingual", ("C[A]SSITT[A]S MAQI MUCOI CALLITI", "mul"),
              "inscription", references=[("@factgrid_id", "external_id", "Q1000294")]),
    Statement(9, "@wikidata_id", "external_id", "Q130529871", "same object: Wikidata"),
    Statement(10, "@factgrid_id", "external_id", "Q1000294", "same object: FactGrid"),
    Statement(11, "@fuzzysl_id", "external_id", "Q74", "same object: Fuzzy-SL"),
    Statement(12, "@linkedogham_id", "external_id", "Y50000081", "same object: LinkedOgham"),
    Statement(13, "@semantickompakkt_id", "external_id", "Q1247", "3D model: Semantic Kompakkt"),
    Statement(14, "@squirrelbase_id", "external_id", "Q48", "FDO / 3D: SquirrelBase"),
    Statement(15, "@ciic_number", "external_id", "81", "CIIC number"),
    Statement(16, "@cisp_id", "external_id", "gares_1", "CISP id"),
]

# Value kinds the importer can already write: items, url/string/external-id
# literals, globe coordinates and monolingual text. References/qualifiers are
# still applied in a later step.
SUPPORTED_VALUE_KINDS_TODAY = {"item", "url", "external_id", "coordinate", "monolingual"}