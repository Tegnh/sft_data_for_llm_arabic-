# -*- coding: utf-8 -*-
"""يحسب الإسناد: يقرأ v2 والمعجم ويكتب build/v3/assign/<region>.jsonl + summary.json + review_v2.jsonl"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L

lex_u = L.usable(L.parse_lexicon())
train = L.load_jsonl(os.path.join(L.ROOT, "sft_train_v2.jsonl"))
val = L.load_jsonl(os.path.join(L.ROOT, "sft_val_v2.jsonl"))
test_q = set()
for t in L.load_jsonl(os.path.join(L.ROOT, "sft_dialect_test.jsonl")):
    for k in ("dialect", "msa"): test_q.add(L.norm(t[k]["messages"][0]["content"]))

def marker_state(row):
    """يعيد (valid_regional, found)"""
    users = "\n".join(L.user_texts(row)); reg = row["meta"]["region"]
    found = L.find_markers(users, lex_u)
    if L.NON_SAUDI.search(users): return False, found
    if reg in L.REGIONS:
        others = [r for r in found if r in L.REGIONS and r != reg]
        return (reg in found and not others), found
    if reg == "saudi_general":
        return ("saudi_general" in found and not [r for r in found if r in L.REGIONS]), found
    return (not found), found

tasks = {}   # task_id -> dict
def add(tid, split, idx, row, reason, note=""):
    if tid in tasks: return
    tasks[tid] = {"task_id": tid, "region": row["meta"]["region"], "type": row["meta"]["type"], "split": split, "reason": reason,
                  "old": {"messages": row["messages"]}, "note": note}

# 1) الإجابات المشتركة بين ≥3 مناطق
groups = collections.defaultdict(list)
for i, r in enumerate(train):
    if r["meta"]["region"] in L.REGIONS: groups[L.norm(L.last_a(r))].append(i)
n_shared = 0
for a, idxs in groups.items():
    regs = {train[i]["meta"]["region"] for i in idxs}
    if len(regs) >= 3:
        n_shared += 1
        idxs_sorted = sorted(idxs, key=lambda i: (not marker_state(train[i])[0], i))
        keep_regs = []
        for i in idxs_sorted:
            rg = train[i]["meta"]["region"]
            if rg not in keep_regs and len(keep_regs) < 2: keep_regs.append(rg)
        for i in idxs:
            if train[i]["meta"]["region"] not in keep_regs:
                add(f"T{i+1}", "train", i, train[i], "new_topic", "إجابة مشتركة بين ≥3 مناطق: اكتب سؤالًا وجوابًا جديدين في موضوع مختلف")
# 2) إجابات مكررة أكثر من 3 مرات (عام)
cnt = collections.Counter(L.norm(L.last_a(r)) for r in train)
seen = collections.Counter()
for i, r in enumerate(train):
    a = L.norm(L.last_a(r)); seen[a] += 1
    if cnt[a] > 3 and seen[a] > 3: add(f"T{i+1}", "train", i, r, "new_topic", "إجابة مكررة أكثر من 3 مرات")
# 3) المؤشرات
stats = collections.Counter()
for split, rows, pre in (("train", train, "T"), ("val", val, "V")):
    for i, r in enumerate(rows):
        tid = f"{pre}{i+1}"
        ok, found = marker_state(r)
        reg = r["meta"]["region"]
        if reg in L.REGIONS or reg == "saudi_general":
            if not ok: add(tid, split, i, r, "add_marker", "لا مؤشر معجمي صالح في السؤال (أو مؤشر منطقة أخرى)"); stats[f"{split}_add_marker_{reg}"] += 1
        else:
            dia = {k: [w for w in v if not L.is_cultural(w)] for k, v in found.items()}
            dia = {k: v for k, v in dia.items() if v}
            if any(k in L.REGIONS for k in dia):
                add(tid, split, i, r, "repair", f"region=none لكن السؤال يحوي مفردات لهجية إقليمية {dia}: أزلها أو صغ السؤال بفصحى"); stats["none_with_regional"] += 1
            elif dia: stats[f"{split}_none_to_saudi_general"] += 1
# 4) أخطاء الصف الأخرى (طول، لهجة في الإجابة، اختراع سياسة، حسابيات)
flag = []
for split, rows, pre in (("train", train, "T"), ("val", val, "V")):
    for i, r in enumerate(rows):
        m = dict(r["meta"]); m.setdefault("split", split); m.setdefault("dialect_markers", []); m.setdefault("confidence", "high"); m.setdefault("source", "v2")
        rr = {"messages": r["messages"], "meta": m}
        errs = [e for e in L.row_errors(rr, lex_u) if not (e.startswith("dialect_markers") or "المؤشر" in e or "مؤشر خاص" in e or e.startswith("region=none") or e.startswith("saudi_general لكن")
                                                            or "سؤال المستخدم يحوي مفردات منطقة" in e or "source" in e)]
        if errs:
            flag.append({"task_id": f"{pre}{i+1}", "errors": errs, "type": r["meta"]["type"], "q": L.first_q(r)[:100], "a": L.last_a(r)[:100]})
# اختراع سياسة/خدمة مؤكد يدويًا: يُنقل إلى needs_review_v3.jsonl ولا يُستبدل (3365 + 639 - 5 = 3999 ثم صف إضافي واحد)
REMOVE = {"T535": "يخترع قدرة/سياسة (لا حاجة للفاتورة ونتحقق من الشراء)", "T564": "يخترع سياسة ضمان تشمل الشحن", "T2378": "يخترع تغطية الضمان لمشكلة تبريد",
          "T2756": "يخترع خدمة (الفنيين لدينا وبيع قطع الغيار)", "T2818": "يخترع سياسة مطابقة سعر"}
trm = []
for tid, why in REMOVE.items():
    row = train[int(tid[1:]) - 1]; tasks.pop(tid, None)
    trm.append({"messages": row["messages"], "meta": dict(row["meta"]), "v2_id": tid, "reason": why, "flagged_by": "assign.py"})
L.write_jsonl(os.path.join(L.V3, "assign", "removed_v2.jsonl"), trm)
flag = [f for f in flag if f["task_id"] not in REMOVE]
L.write_jsonl(os.path.join(L.V3, "assign", "review_v2.jsonl"), flag)
# توزيع على الوكلاء (المناطق: لصاحبها؛ الباقي دورانيًا)
by = collections.defaultdict(list); rr = 0
for t in tasks.values():
    o = t["region"] if t["region"] in L.REGIONS else L.REGIONS[rr % 5]
    if t["region"] not in L.REGIONS: rr += 1
    by[o].append(t)
for reg in L.REGIONS:
    L.write_jsonl(os.path.join(L.V3, "assign", f"{reg}.jsonl"), sorted(by[reg], key=lambda t: t["task_id"]))
summ = {"shared_answer_groups_ge3": n_shared, "tasks_total": len(tasks), "by_owner": {k: len(v) for k, v in by.items()},
        "by_reason": dict(collections.Counter(t["reason"] for t in tasks.values())), "stats": dict(stats), "flagged_other_errors": len(flag)}
json.dump(summ, open(os.path.join(L.V3, "assign", "summary.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(summ, ensure_ascii=False, indent=1))
