# Testfall: Q3 "Ogham Stone UCC Stone Corridor IV" (CIIC 81)
# Prüft alle vier lokal/föderiert-Kombinationen von Property und Wert.
# Rein technischer Test — die inhaltliche Bedeutung der Werte ist hier egal.
#
# Bekannt gut auf der Instanz:
#   lokale Item-Property        : P1
#   föderierte Property         : P5572 (Wikidata)
#   lokale Item-Werte           : Q2, Q4
#   föderierte Item-Werte       : Q5, Q837161, Q2016147 (Wikidata)

# ============================================================
# A) sollten NEU ANGELEGT werden (an Q3 noch nicht vorhanden)
# ============================================================

# 1) lokale Property    + lokaler Item-Wert
Q3	P1	Q2

# 2) lokale Property    + föderierter Wikidata-Item-Wert
Q3	P1	wd:Q837161

# 3) föderierte Property + lokaler Item-Wert
Q3	wd:P5572	Q2

# 4) föderierte Property + föderierter Wikidata-Item-Wert
Q3	wd:P5572	wd:Q2016147

# ============================================================
# B) sollten ÜBERSPRUNGEN werden (schon vorhanden -> testet skip_existing)
#    - einmal lokale, einmal föderierte Property
# ============================================================
Q3	P1	Q4
Q3	wd:P5572	wd:Q5
