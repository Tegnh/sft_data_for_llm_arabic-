import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
lex = L.parse_lexicon()
p = L.lexicon_problems(lex)
for r in L.REGIONS + ["saudi_general"]:
    print(r, len(lex.get(r, [])), "مفردة")
if p:
    print("مشكلات:"); [print(" -", x) for x in p]; sys.exit(1)
print("OK")
