# Example statements for the QuickStatements-like API importer.
# Format: <local subject item> <TAB> <property> <TAB> <value>
# Blank lines and lines starting with '#' are ignored.
#
# Property column : P...  = local property     | wd:P... / Wikidata URI = federated
# Value column    : Q...  = local item value   | wd:Q... / Wikidata URI = federated
#
# All four combinations are supported:

# 1) local property + local item value
Q3	P1	Q4

# 2) local property + federated Wikidata item value
Q3	P1	http://www.wikidata.org/entity/Q2016147
Q3	P1	wd:Q5

# 3) federated Wikidata property + local item value
Q3	wd:P5572	Q4

# 4) federated Wikidata property + federated Wikidata item value
Q3	wd:P5572	wd:Q5
