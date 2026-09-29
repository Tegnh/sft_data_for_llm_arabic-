# -*- coding: utf-8 -*-
"""المرحلة 4: أزواج النص المعطى. train: 300 زوجًا من 104 فقرات (كل فقرة 3 مرات كحد أقصى)،
و val: أزواج من 35 فقرة منفصلة تمامًا. 30% من أسئلة train بلهجة سعودية."""
import os, sys, random, re, collections
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from data_pairs_geo import GEO
from data_pairs_hist import HIST
from data_pairs_sci import SCI
from data_pairs_ext import EXT, FIX
from gen_dialect import LEX, REGIONS, OPEN, CLOSE

def load_paras():
    out = {"geo": [], "hist": [], "sci": []}
    for name, L in (("geo", GEO), ("hist", HIST), ("sci", SCI)):
        for i, (p, qa, un) in enumerate(L):
            p2 = p + (" " + EXT[name][i] if i in EXT[name] else "")
            qa2 = []
            for k, (q, a) in enumerate(qa):
                if (name, i, k) in FIX:
                    nq, na = FIX[(name, i, k)]
                    q, a = (nq or q), na
                qa2.append((q, a))
            assert 25 <= wc(p2) <= 80, (name, i, wc(p2))
            for q, a in qa2: assert a in p2, (name, i, a)
            out[name].append(dict(p=p2, qa=qa2, un=un, src=name))
    return out

REFUSE_T = [
 "النص لا يذكر {t}.", "لا يتضمن النص أي معلومة عن {t}.", "لم يرد في النص ذكر {t}.",
 "لا أجد في النص ما يجيب عن هذا السؤال، فهو لا يتحدث عن {t}.", "النص لا يتطرق إلى {t}.", "لا توجد في النص إشارة إلى {t}.",
 "هذه المعلومة غير موجودة في النص، إذ لا يذكر {t}.", "لا يمكن الإجابة اعتمادًا على النص، فهو لا يذكر {t}.", "النص لا يبيّن {t}.",
 "ليس في النص ما يدل على {t}.", "لم يتناول النص {t}.", "لا يحدد النص {t}.", "بحسب النص، لا توجد معلومات عن {t}.",
 "النص المعطى لا يذكر {t}، فلا أستطيع الجزم بذلك.", "لا يشير النص إلى {t}.", "لا يوضح النص {t}.",
 "المعلومة المطلوبة غير واردة في النص؛ فهو لا يذكر {t}.", "النص لا يقدّم أي تفاصيل عن {t}.", "لا تحتوي الفقرة على معلومة عن {t}.",
 "لا يرد في هذا النص شيء عن {t}.", "الفقرة لا تذكر {t}، لذا لا أستطيع الإجابة.", "لا يعرض النص أي بيان عن {t}.",
]
MSA_FRAMES = ["اقرأ النص التالي ثم أجب عن السؤال.\nالنص: {p}\nالسؤال: {q}", "النص: {p}\nالسؤال: {q}", "{p}\n\nبحسب النص، {q}", "اعتمد على النص فقط في الإجابة.\n{p}\n{q}"]
DIA_FRAMES = ["اقرا هالنص وجاوبني:\n{p}\n{q}", "النص:\n{p}\n\nسؤالي: {q}", "{p}\n\nمن الكلام اللي فوق، {q}", "اقرأ هالفقرة وجاوبني على قد النص:\n{p}\n{q}"]

def to_dialect(q, region):
    L = LEX[region]
    t = q.split(" ")
    f = t[0]
    def rest(k=1): return " ".join(t[k:])
    if f in ("ما", "ماذا"):
        if len(t) > 1 and t[1] in ("هو", "هي"): return "%s %s" % (L["w"], q.split(" ", 1)[1])
        return "%s %s" % (L["w"], rest())
    if f == "أين": return "%s %s" % (L["e"], rest())
    if f == "لماذا": return "%s %s" % (L["y"], rest())
    if f == "كيف": return "%s %s" % (L["h"], rest())
    if f == "من" and len(t) > 1 and not t[1].startswith("أي") and t[1] != "أين": return "%s %s" % (L["m"], rest())
    if f == "بماذا": return "بـ%s %s" % (L["w"], rest())
    if f == "مم": return "من %s %s" % (L["w"], rest())
    return q

def build(seed=4):
    rng = random.Random(seed)
    P = load_paras()
    allp = P["geo"] + P["hist"] + P["sci"]
    train_p = P["geo"][:32] + P["hist"][:33] + P["sci"][:39]
    val_p = P["geo"][32:] + P["hist"][33:] + P["sci"][39:]
    rng.shuffle(train_p)
    # 92 فقرة بثلاثة أسئلة (سؤالان مجابان + سؤال بلا جواب)، و12 فقرة بسؤالين مجابين => 300
    items = []   # (para, q, a, kind, topic)
    for i, d in enumerate(train_p):
        withun = i < 92
        for q, a in d["qa"]: items.append((d, q, a, "ans", None))
        if withun: items.append((d, d["un"][0][0], None, "un", d["un"][0][1]))
    assert len(items) == 300, len(items)
    rng.shuffle(items)
    # 90 سؤالًا بلهجة سعودية (18 لكل منطقة) من المجاب وغير المجاب
    dia_idx = set(rng.sample(range(len(items)), 90))
    reg_cycle = []
    for r in REGIONS: reg_cycle += [r] * 18
    rng.shuffle(reg_cycle)
    rows = []; ti = 0; di = 0; fi = collections.Counter()
    for k, (d, q, a, kind, topic) in enumerate(items):
        if k in dia_idx:
            region = reg_cycle[di]; di += 1
            qq = to_dialect(q, region)
            fr = DIA_FRAMES[fi["d"] % len(DIA_FRAMES)]; fi["d"] += 1
            user = fr.format(p=d["p"], q=qq)
        else:
            region = "none"; qq = q
            fr = MSA_FRAMES[fi["m"] % len(MSA_FRAMES)]; fi["m"] += 1
            user = fr.format(p=d["p"], q=qq)
        if kind == "un":
            ans = REFUSE_T[ti % len(REFUSE_T)].format(t=topic); ti += 1
            typ = "text_unanswerable"
        else:
            ans = a; typ = "text_answerable"
        rows.append(row(user, ans, typ, region))
    return rows, val_p

if __name__ == "__main__":
    log("المرحلة 4: بدء بناء أزواج النص المعطى")
    rows, val_p = build()
    w = BatchWriter(os.path.join(ROOT, "build", "out", "pairs_train.jsonl"), "pairs_train")
    for r in rows: w.add(r)
    w.close()
    c = collections.Counter(r["meta"]["type"] for r in rows); print(c)
    print(collections.Counter(r["meta"]["region"] for r in rows))
    print("distinct refusal templates:", len(set(re.sub(r"(عن|ذكر|إلى|في|على|يذكر) .*", "", r["messages"][1]["content"]) for r in rows if r["meta"]["type"] == "text_unanswerable")))
    print("paras", len(set(r["messages"][0]["content"].split("\n")[1] if False else "" for r in rows)))
