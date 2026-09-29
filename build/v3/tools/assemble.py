# -*- coding: utf-8 -*-
"""يجمع النسخة النهائية: صفوف v2 المحتفظ بها (مع ترقية meta) + دفعات v3 المقبولة. يكتب:
  build/v3/sft_train_v3.jsonl  build/v3/sft_val_v3.jsonl  build/v3/needs_review_v3.jsonl"""
import sys, os, glob, json, random, collections
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L

lex_u = L.usable(L.parse_lexicon())
tasks = {}
for f in glob.glob(os.path.join(L.V3, "assign", "[a-z]*.jsonl")):
    if os.path.basename(f) in ("review_v2.jsonl", "removed_v2.jsonl"): continue
    for t in L.load_jsonl(f): tasks[t["task_id"]] = t
removed = {x["v2_id"]: x for x in L.load_jsonl(os.path.join(L.V3, "assign", "removed_v2.jsonl"))}
qa_fail = set()
qpath = os.path.join(L.V3, "qa", "failed_ids.json")
if os.path.exists(qpath): qa_fail = set(json.load(open(qpath)))   # معرفات صفوف فاشلة في المراجعة (agent:batch:index)

parts = []
for f in sorted(glob.glob(os.path.join(L.V3, "parts", "*", "batch_*.jsonl"))):
    agent = f.split("/")[-2]; b = os.path.basename(f)[:-6]
    for i, r in enumerate(L.load_jsonl(f)):
        r["_qid"] = f"{agent}:{b}:{i}"; parts.append(r)
replaced = {r["task_id"] for r in parts if r.get("task_id") and r["_qid"] not in qa_fail}
review_out = list(removed.values())
for r in parts:
    if r["_qid"] in qa_fail: review_out.append({"messages": r["messages"], "meta": r["meta"], "qa_id": r["_qid"], "reason": "failed qa"})

def upgrade(row, split):
    m = row["meta"]; users = "\n".join(L.user_texts(row)); reg = m["region"]
    found = L.find_markers(users, lex_u)
    if reg in L.REGIONS:
        mk = [w for w in found.get(reg, []) + found.get("saudi_general", []) if w in users]
    elif reg == "saudi_general" or (reg == "none" and any(not L.is_cultural(w) for w in found.get("saudi_general", []))):
        mk = [w for w in found.get("saudi_general", []) if w in users]; reg = "saudi_general" if mk else "none"
    else:
        mk = []
    mk = list(dict.fromkeys(mk))
    conf = "high"
    for w in mk:
        c = lex_u.get(reg, {}).get(w) or lex_u["saudi_general"].get(w)
        if c == "medium": conf = "medium"
    return {"messages": row["messages"], "meta": {"type": m["type"], "region": reg, "split": split, "dialect_markers": mk, "confidence": conf, "source": "v2"}}

ovr = {}
op = os.path.join(L.V3, "patches", "v2_overrides.json")
if os.path.exists(op): ovr = json.load(open(op, encoding="utf-8"))
out = {"train": [], "val": []}; kept = collections.Counter()
for pre, name, split in (("T", "sft_train_v2.jsonl", "train"), ("V", "sft_val_v2.jsonl", "val")):
    for i, r in enumerate(L.load_jsonl(os.path.join(L.ROOT, name))):
        tid = f"{pre}{i+1}"
        if tid in removed or tid in replaced: continue
        if tid in ovr:
            if ovr[tid].get("review"):
                review_out.append({"messages": r["messages"], "meta": r["meta"], "v2_id": tid, "reason": ovr[tid]["review"], "flagged_by": "manual-scan", "replacement": "نفس السؤال بإجابة مصححة داخل الملف النهائي"})
            r = json.loads(json.dumps(r))
            if "q" in ovr[tid]: r["messages"][0]["content"] = ovr[tid]["q"]
            if "a" in ovr[tid]: r["messages"][-1]["content"] = ovr[tid]["a"]
        out[split].append(upgrade(r, split)); kept[split] += 1
for r in parts:
    if r["_qid"] in qa_fail: continue
    row = {"messages": r["messages"], "meta": r["meta"]}
    out[r["meta"]["split"]].append(row)
rng = random.Random(42)
for k in out: rng.shuffle(out[k])
L.write_jsonl(os.path.join(L.V3, "sft_train_v3.jsonl"), out["train"])
L.write_jsonl(os.path.join(L.V3, "sft_val_v3.jsonl"), out["val"])
L.write_jsonl(os.path.join(L.V3, "needs_review_v3.jsonl"), review_out)
print("v2 المحتفظ به:", dict(kept), "| train:", len(out["train"]), "| val:", len(out["val"]), "| needs_review_v3:", len(review_out))
