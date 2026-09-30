# -*- coding: utf-8 -*-
"""يحوّل مسودة نصية مضغوطة إلى دفعة JSONL مصدَّقة.
الاستعمال: mk_batch.py <agent> <mode> <infile> [--batch N]
modes:
  edit      : كل سطر  tid<TAB>old<TAB>new[<TAB>new_answer]  — يعدّل رسالة المستخدم في مهمة add_marker/repair (old='^' إضافة في البداية، '$' في النهاية)
  newtask   : كل سطر  tid<TAB>type<TAB>question<TAB>answer   — صف جديد كليًا يستبدل مهمة new_topic
  new       : كل سطر  type<TAB>region<TAB>split<TAB>turns   — turns مفصولة بـ ||| (سؤال|||جواب[|||سؤال|||جواب])؛ ⏎ = سطر جديد
الصفوف السليمة تُكتب في parts/<agent>/batch_NNN.jsonl، والمرفوضة في parts/<agent>/rejects_NNN.txt مع الأسباب.
"""
import sys, os, json, re, glob, collections
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L

agent, mode, infile = sys.argv[1:4]
lex_u = L.usable(L.parse_lexicon())
tasks = {}
for f in glob.glob(os.path.join(L.V3, "assign", "*.jsonl")):
    if os.path.basename(f) in ("review_v2.jsonl", "removed_v2.jsonl"): continue
    for t in L.load_jsonl(f): tasks[t["task_id"]] = t

def unesc(s): return s.replace("⏎", "\n").strip()

def make_meta(typ, region, split, users):
    found = L.find_markers(users, lex_u)
    mk = []
    if region in L.REGIONS: mk = found.get(region, []) + [w for w in found.get("saudi_general", [])]
    elif region == "saudi_general": mk = found.get("saudi_general", [])
    mk = [w for w in dict.fromkeys(mk) if w in users]
    conf = "high"
    for w in mk:
        c = lex_u.get(region, {}).get(w) or lex_u["saudi_general"].get(w)
        if c == "medium": conf = "medium"
    return {"type": typ, "region": region, "split": split, "dialect_markers": mk, "confidence": conf, "source": f"v3-{agent}"}

def build_rows():
    out = []
    for ln, line in enumerate(open(infile, encoding="utf-8"), 1):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"): continue
        p = line.split("\t") if "\t" in line else [x.strip() for x in line.split("¦")]
        try:
            if mode == "edit":
                tid = p[0]; rest = p[1:]
                ans = None
                if rest and rest[-1].startswith("ANS:"): ans = rest[-1][4:]; rest = rest[:-1]
                t = tasks[tid]; msgs = json.loads(json.dumps(t["old"]["messages"]))
                u = msgs[0]["content"]
                for k in range(0, len(rest) - 1, 2):
                    old, new = rest[k], rest[k + 1].replace("⏎", "\n")
                    if old == "^": u = new + " " + u
                    elif old == "$": u = u + " " + new
                    else:
                        if u.count(old) < 1: raise ValueError(f"old غير موجودة في السؤال: {old}")
                        u = u.replace(old, new, 1)
                msgs[0]["content"] = u
                if ans is not None: msgs[-1]["content"] = unesc(ans)
                row = {"task_id": tid, "messages": msgs, "meta": make_meta(t["type"], t["region"], t["split"], "\n".join(L.user_texts({"messages": msgs})))}
            elif mode == "newtask":
                tid, typ, q, a = p[0], p[1], unesc(p[2]), unesc(p[3])
                t = tasks[tid]; msgs = [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
                row = {"task_id": tid, "messages": msgs, "meta": make_meta(typ, t["region"], t["split"], q)}
            elif mode == "new":
                typ, region, split, turns = p[0], p[1], p[2], p[3].split("|||")
                msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": unesc(x)} for i, x in enumerate(turns)]
                row = {"messages": msgs, "meta": make_meta(typ, region, split, "\n".join(m["content"] for m in msgs if m["role"] == "user"))}
            else: raise ValueError("mode")
            out.append((ln, line, row))
        except Exception as e:
            out.append((ln, line, "ERR: %s" % e))
    return out

# ---- المرجع العالمي لفحص التكرار
def pool_index(exclude_files=()):
    """يحمّل صفوف v2 المحتفظ بها + الدفعات الموجودة"""
    rows = []
    replaced = set()
    for f in sorted(glob.glob(os.path.join(L.V3, "parts", "*", "batch_*.jsonl"))):
        if f in exclude_files: continue
        for r in L.load_jsonl(f):
            rows.append(r)
            if r.get("task_id"): replaced.add(r["task_id"])
    removed = {x["v2_id"] for x in L.load_jsonl(os.path.join(L.V3, "assign", "removed_v2.jsonl"))}
    v2 = []
    for pre, name in (("T", "sft_train_v2.jsonl"), ("V", "sft_val_v2.jsonl")):
        for i, r in enumerate(L.load_jsonl(os.path.join(L.ROOT, name))):
            if f"{pre}{i+1}" in replaced or f"{pre}{i+1}" in removed: continue
            if f"{pre}{i+1}" in tasks: continue   # ستُستبدل (أو استُبدلت) بصف جديد
            rr = {"messages": r["messages"], "meta": {"type": r["meta"]["type"], "region": r["meta"]["region"], "split": "train" if pre == "T" else "val"}}
            v2.append(rr)
    test = []
    for t in L.load_jsonl(os.path.join(L.ROOT, "sft_dialect_test.jsonl")):
        for k in ("dialect", "msa"): test.append(L.norm(t[k]["messages"][0]["content"]))
    return v2 + rows, set(test), {f"{p}" for p in replaced}

if __name__ == "__main__":
    bn = None
    if "--batch" in sys.argv: bn = int(sys.argv[sys.argv.index("--batch") + 1])
    pdir = os.path.join(L.V3, "parts", agent); os.makedirs(pdir, exist_ok=True)
    if bn is None:
        ex = glob.glob(os.path.join(pdir, "batch_*.jsonl")); bn = len(ex) + 1
    outp = os.path.join(pdir, f"batch_{bn:03d}.jsonl")
    items = build_rows()
    pool, test_q, done_tasks = pool_index(exclude_files=(outp,))
    ans_cnt = collections.Counter(L.norm(L.last_a(r)) for r in pool if r["meta"]["split"] == "train")
    ans_reg = collections.defaultdict(set)
    for r in pool:
        if r["meta"]["split"] == "train" and r["meta"]["region"] in L.REGIONS: ans_reg[L.norm(L.last_a(r))].add(r["meta"]["region"])
    ans_val = {L.norm(L.last_a(r)) for r in pool if r["meta"]["split"] == "val"}
    q_all = {L.norm(L.first_q(r)) for r in pool}
    shing_tr, shing_va = set(), set()
    good, rej = [], []
    for ln, line, row in items:
        if isinstance(row, str): rej.append((ln, line, [row])); continue
        errs = L.row_errors(row, lex_u, agent=agent)
        if row.get("task_id") and row["task_id"] in done_tasks: errs.append("task_id منجز سابقًا")
        a, q = L.norm(L.last_a(row)), L.norm(L.first_q(row))
        if q in q_all or q in test_q: errs.append("السؤال مكرر في المجموعة أو dialect_test")
        if row["meta"]["split"] == "train":
            if ans_cnt[a] >= 3: errs.append("الإجابة مكررة 3 مرات في train")
            rg = row["meta"]["region"]
            if rg in L.REGIONS and rg not in ans_reg[a] and len(ans_reg[a]) >= 2: errs.append("الإجابة في أكثر من منطقتين")
        elif a in ans_val: errs.append("إجابة val مكررة")
        if not errs:
            good.append(row); q_all.add(q)
            if row["meta"]["split"] == "train":
                ans_cnt[a] += 1
                if row["meta"]["region"] in L.REGIONS: ans_reg[a].add(row["meta"]["region"])
            else: ans_val.add(a)
        else: rej.append((ln, line, errs))
    if good: L.write_jsonl(outp, good)
    if rej:
        with open(os.path.join(pdir, f"rejects_{bn:03d}.txt"), "w", encoding="utf-8") as f:
            for ln, line, errs in rej: f.write(f"L{ln}\t{'; '.join(errs)}\t{line}\n")
    print(f"{agent} batch_{bn:03d}: مقبول {len(good)} / مرفوض {len(rej)}" + ("" if good else " (لم يُكتب ملف)"))
    for ln, line, errs in rej: print(f"  L{ln}: {'; '.join(errs)[:200]} | {line[:70]}")
