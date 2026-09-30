import sys, os, glob, json, collections
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
prog = {"agents": {}, "totals": collections.Counter()}
tasks = {}
for f in glob.glob(os.path.join(L.V3, "assign", "*.jsonl")):
    if os.path.basename(f) in ("review_v2.jsonl", "removed_v2.jsonl"): continue
    for t in L.load_jsonl(f): tasks[t["task_id"]] = t
done = set()
for d in sorted(glob.glob(os.path.join(L.V3, "parts", "*"))):
    a = os.path.basename(d); c = collections.Counter(); c["batches"] = 0
    for f in sorted(glob.glob(os.path.join(d, "batch_*.jsonl"))):
        c["batches"] += 1
        for r in L.load_jsonl(f):
            c["rows_" + r["meta"]["split"]] += 1
            if r.get("task_id"): c["tasks_done"] += 1; done.add(r["task_id"])
            else: c["new_" + r["meta"]["split"]] += 1
            c["type_" + r["meta"]["type"]] += 1
    prog["agents"][a] = dict(c)
pend = [t for t in tasks if t not in done]
prog["tasks_total"] = len(tasks); prog["tasks_done"] = len(done); prog["tasks_pending"] = len(pend)
prog["pending_by_owner"] = dict(collections.Counter(tasks[t]["region"] for t in pend))
prog["totals"] = {"rows_train": sum(a.get("rows_train", 0) for a in prog["agents"].values()), "rows_val": sum(a.get("rows_val", 0) for a in prog["agents"].values())}
json.dump(prog, open(os.path.join(L.V3, "progress.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(prog, ensure_ascii=False, indent=1))
