# -*- coding: utf-8 -*-
"""المرحلة 5: sft_val_v2.jsonl (300 صف فريد) و sft_dialect_test.jsonl (150 عنصرًا، 30 لكل منطقة)."""
import os, sys, random, re, json, collections
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from gen_dialect import LEX, REGIONS, sub, decorate
from gen_pairs import load_paras, REFUSE_T, MSA_FRAMES
from data_val1 import VAL_INFO, VAL_ADV, VAL_REF
from data_val2 import VAL_SUM, VAL_EXT, VAL_REW
from data_dt_info import DT_INFO
from data_dt_adv import DT_ADV, DT_REF

SUM_F = ["لخص النص التالي في جملة واحدة:\n{t}", "اكتب ملخصًا قصيرًا للنص الآتي:\n{t}", "أوجز الفقرة التالية:\n{t}",
         "ما الفكرة الرئيسة في النص الآتي؟\n{t}", "اختصر ما يلي في جملة:\n{t}", "لخّص لي هذه الفقرة:\n{t}"]
EXT_F = ["{task}\nالنص: {t}", "النص: {t}\n{task}", "{task}\n{t}"]
REW_F = ["{i}\n{s}", "{i}\nالجملة: {s}", "{s}\n{i}"]

def dialect_q(tpl, region, rng):
    return decorate(sub(tpl, region), region, rng, allow_city=True)

def build_val_and_test(seed=5):
    rng = random.Random(seed)
    # ---- تقسيم مواد الاختبار اللهجي
    pool = [("informational", m, d, a) for (m, d, a) in DT_INFO] + [("advice", m, d, a) for (m, d, a) in DT_ADV] + [("refusal", m, d, a) for (m, d, a) in DT_REF]
    byt = collections.defaultdict(list)
    for it in pool: byt[it[0]].append(it)
    for v in byt.values(): rng.shuffle(v)
    val_dia = byt["informational"][:33] + byt["advice"][:14] + byt["refusal"][:3]
    test_dia = byt["informational"][33:] + byt["advice"][14:] + byt["refusal"][3:]
    assert len(val_dia) == 50 and len(test_dia) == 150, (len(val_dia), len(test_dia))
    # ---- val
    rows = []
    for q, a in VAL_INFO: rows.append(row(q, a, "informational"))
    for q, a in VAL_ADV: rows.append(row(q, a, "advice"))
    for q, a in VAL_REF: rows.append(row(q, a, "refusal"))
    for i, (t, s) in enumerate(VAL_SUM): rows.append(row(SUM_F[i % len(SUM_F)].format(t=t), s, "summarize"))
    for i, (t, task, a) in enumerate(VAL_EXT): rows.append(row(EXT_F[i % len(EXT_F)].format(t=t, task=task), a, "extract"))
    for i, (ins, s, o) in enumerate(VAL_REW): rows.append(row(REW_F[i % len(REW_F)].format(i=ins, s=s), o, "rewrite"))
    # لهجات: 10 لكل منطقة
    regs = []
    for r in REGIONS: regs += [r] * 10
    rng.shuffle(regs)
    for (typ, m, d, a), region in zip(val_dia, regs):
        rows.append(row(dialect_q(d, region, rng), a, typ, region))
    # نص معطى من فقرات val
    P = load_paras()
    train_ans = set(norm(json.loads(l)["messages"][1]["content"]) for l in open(os.path.join(ROOT, "sft_train_v2.jsonl"), encoding="utf-8"))
    val_p = P["geo"][32:] + P["hist"][33:] + P["sci"][39:]
    ans_items, un_items = [], []
    for d in val_p:
        for q, a in d["qa"]:
            if norm(a) not in train_ans: ans_items.append((d, q, a))
        un_items.append((d, d["un"][0][0], d["un"][0][1]))
    rng.shuffle(ans_items); rng.shuffle(un_items)
    use_ans = []
    seen_par = collections.Counter()
    for d, q, a in ans_items:
        if seen_par[d["p"]] < 2 and len(use_ans) < 40:
            use_ans.append((d, q, a)); seen_par[d["p"]] += 1
    use_un = []
    for d, q, t in un_items:
        if seen_par[d["p"]] < 3 and len(use_un) < 12:
            use_un.append((d, q, t)); seen_par[d["p"]] += 1
    for k, (d, q, a) in enumerate(use_ans):
        rows.append(row(MSA_FRAMES[k % 4].format(p=d["p"], q=q), a, "text_answerable"))
    tpl_order = list(range(len(REFUSE_T))); rng.shuffle(tpl_order)
    for k, (d, q, t) in enumerate(use_un):
        rows.append(row(MSA_FRAMES[(k + 1) % 4].format(p=d["p"], q=q), REFUSE_T[tpl_order[k]].format(t=t), "text_unanswerable"))
    rng.shuffle(rows)
    # ---- dialect test: 30 لكل منطقة
    rng.shuffle(test_dia)
    per = {r: [] for r in REGIONS}
    tcount = collections.Counter()
    for typ, m, d, a in sorted(test_dia, key=lambda x: x[0]):
        # وزّع الأنواع بالتساوي: اختر المنطقة الأقل امتلاءً بهذا النوع
        r = sorted(REGIONS, key=lambda rr: (len(per[rr]) >= 30, tcount[(rr, typ)], len(per[rr]), rng.random()))[0]
        per[r].append((typ, m, d, a)); tcount[(r, typ)] += 1
    assert all(len(v) == 30 for v in per.values()), {k: len(v) for k, v in per.items()}
    test = []; n = 0
    for r in REGIONS:
        for typ, m, d, a in per[r]:
            n += 1
            dq = dialect_q(d, r, rng)
            test.append({"pair_id": "dt%03d" % n, "region": r,
                         "dialect": {"messages": [{"role": "user", "content": dq}, {"role": "assistant", "content": a}]},
                         "msa": {"messages": [{"role": "user", "content": m}, {"role": "assistant", "content": a}]},
                         "reference_answer": a, "meta": {"type": typ, "region": r}})
    rng.shuffle(test)
    return rows, test

if __name__ == "__main__":
    log("المرحلة 5: بدء بناء val و dialect_test")
    rows, test = build_val_and_test()
    w = BatchWriter(os.path.join(ROOT, "sft_val_v2.jsonl"), "sft_val_v2")
    for r in rows: w.add(r)
    w.close()
    w = BatchWriter(os.path.join(ROOT, "sft_dialect_test.jsonl"), "sft_dialect_test")
    for t in test: w.add(t)
    w.close()
    print("val", len(rows), collections.Counter(r["meta"]["type"] for r in rows))
    print(collections.Counter(r["meta"]["region"] for r in rows))
    print("test", len(test), collections.Counter(t["region"] for t in test), collections.Counter(t["meta"]["type"] for t in test))
    ref = sum(1 for r in rows if r["meta"]["type"] in ("refusal", "text_unanswerable"))
    print("val refusal", ref, ref / len(rows))
