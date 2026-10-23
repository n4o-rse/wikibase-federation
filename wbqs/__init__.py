"""wbqs — QuickStatements-to-Wikibase-API importer (local + federated)."""

from .parser import (
    ParseError,
    Statement,
    parse_line,
    parse_property,
    parse_qs_file,
    parse_value,
)

__version__ = "1.2.0"

__all__ = [
    "ParseError",
    "Statement",
    "parse_line",
    "parse_property",
    "parse_qs_file",
    "parse_value",
    "__version__",
]
