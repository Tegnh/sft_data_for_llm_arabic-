import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
reg, reason = sys.argv[1], sys.argv[2]
lo, hi = int(sys.argv[3]), int(sys.argv[4])
rows = [r for r in L.load_jsonl(os.path.join(L.V3, "assign", f"{reg}.jsonl")) if r["reason"] == reason]
done = set()
import glob
for f in glob.glob(os.path.join(L.V3, "parts", "*", "batch_*.jsonl")):
    for r in L.load_jsonl(f):
        if r.get("task_id"): done.add(r["task_id"])
rows = [r for r in rows if r["task_id"] not in done]
print(f"# {reg}/{reason}: متبقٍ {len(rows)}")
for r in rows[lo:hi]:
    q = r["old"]["messages"][0]["content"].replace("\n", "⏎")
    a = r["old"]["messages"][-1]["content"].replace("\n", "⏎")
    if reason == "add_marker": print(f"{r['task_id']}|{r['type'][:6]}|{r['split'][0]}|{r['region'][:3]}|{q[:200]}")
    else: print(f"{r['task_id']}|{r['type']}|{r['split']}|{q[:90]} => {a[:60]}")
