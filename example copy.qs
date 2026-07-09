# Example statements for the QuickStatements-like API importer.
# Format: <local item> <TAB> <property> <TAB> <value>
# Blank lines and lines starting with '#' are ignored.

# 1) Local item -> local item value
Q3	P1	Q4

# 2) Local item -> federated Wikidata item (full entity URI) -- the federation case
Q3	P1	http://www.wikidata.org/entity/Q2016147

# 3) Also accepted: the compact wd: prefix for a federated Wikidata item
Q3	P1	wd:Q5

# 4) A bare Q-ID is LOCAL by default; pass --federate-bare-qids to treat it as Wikidata
Q3	P1	Q837161
