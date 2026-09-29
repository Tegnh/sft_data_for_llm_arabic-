import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
u = L.usable(L.parse_lexicon())
for t in sys.argv[1:]:
    print(t, "=>", L.find_markers(t, u))
