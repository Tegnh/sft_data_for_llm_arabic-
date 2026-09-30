import sys, os, glob, difflib
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
tasks = {}
for f in glob.glob(os.path.join(L.V3, "assign", "[a-z]*.jsonl")):
    if "review" in f or "removed" in f: continue
    for t in L.load_jsonl(f): tasks[t["task_id"]] = t
bad = []
for f in sorted(glob.glob(os.path.join(L.V3, "parts", "*", "batch_*.jsonl"))):
    for r in L.load_jsonl(f):
        t = tasks.get(r.get("task_id"))
        if not t or t["reason"] != "new_topic": continue
        ra = difflib.SequenceMatcher(None, L.norm(L.last_a(r)), L.norm(t["old"]["messages"][-1]["content"])).ratio()
        if ra > 0.6: bad.append((round(ra, 2), r["task_id"], f.split("/")[-2], L.last_a(r)[:60]))
for b in sorted(bad, reverse=True): print(b)
print(len(bad), "مهمة new_topic تشبه القديمة")
