import sys, os, glob, json
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
rows = []
for f in sorted(glob.glob(os.path.join(L.V3, "parts", "*", "batch_*.jsonl"))):
    agent = f.split("/")[-2]; b = os.path.basename(f)[:-6]
    for i, r in enumerate(L.load_jsonl(f)):
        r["qa_id"] = f"{agent}:{b}:{i}"; rows.append(r)
skip = sys.argv[1:]   # وكلاء يُستثنون من المراجعة اليدوية
rows = [r for r in rows if r["qa_id"].split(":")[0] not in skip]
for k in range(0, len(rows), 50):
    L.write_jsonl(os.path.join(L.V3, "qa", "in", f"qa_{k//50+1:03d}.jsonl"), rows[k:k+50])
print(len(rows), "صفًا في", (len(rows) + 49) // 50, "دفعة")
