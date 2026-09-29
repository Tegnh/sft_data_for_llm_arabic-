import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
n = sys.argv[1]
for i, r in enumerate(L.load_jsonl(os.path.join(L.V3, "qa", "in", f"qa_{int(n):03d}.jsonl"))):
    m = r["messages"]
    q = m[0]["content"].replace("\n", "⏎"); a = m[1]["content"].replace("\n", "⏎")
    extra = " ‖ " + m[2]["content"].replace("\n", "⏎")[:40] + " => " + m[3]["content"].replace("\n", "⏎")[:50] if len(m) > 2 else ""
    print(f"{i:02d}|{r['meta']['type'][:5]}|{r['meta']['region'][:3]}|{q[:92]} => {a[:42]}{extra}")
