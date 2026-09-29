# -*- coding: utf-8 -*-
"""المرحلة 2: تنظيف train -> sft_train_v2.jsonl (الجزء الأول: الصفوف الأصلية المنظفة والمعاد كتابتها).
يقرأ sft_train.jsonl فقط ولا يعدّله. المخرجات الوسيطة في build/out/."""
import os, sys, re, json, collections
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from data_python import python_rows
from data_refusals import refusal_rows, REF
from data_train_fix import *

OUT = os.path.join(ROOT, "build", "out"); os.makedirs(OUT, exist_ok=True)
A = lambda r: r["messages"][-1]["content"]
Q = lambda r: r["messages"][-2]["content"]

def toks(s): return set(norm(s).split())
def pick_diverse(qs, k=3):
    """اختيار k صياغات هي الأبعد عن بعضها (جاكارد على الكلمات)."""
    if len(qs) <= k: return list(range(len(qs)))
    T = [toks(q) for q in qs]
    dist = lambda i, j: 1 - len(T[i] & T[j]) / max(1, len(T[i] | T[j]))
    chosen = [min(range(len(qs)), key=lambda i: len(qs[i]))]
    while len(chosen) < k:
        best = max((i for i in range(len(qs)) if i not in chosen), key=lambda i: (min(dist(i, j) for j in chosen), -i))
        chosen.append(best)
    return sorted(chosen)

CUSTOMER = re.compile(r"(حالة طلب|طلبي|شحنتي|شحنة|الشحنة|استرجاع|استرداد|ألغي|احجز|أحجز|أطلب|أشتري|بالتقسيط|تقبلون|عندكم|فيه توصيل|توصيل|"
                      r"شكوى|أشتكي|بطاقة الهدية|الفرع|المندوب|الطلب وصل|طلبت|وصلني|المبلغ اتخصم|اتخصم|الجهاز فيه|الخدمة كانت|الموظف تعامل|"
                      r"باقة إنترنت|رقم الطلب|طلب الصيانة|جهازي اللي|كيف أفعّل|ابغى استبدال|أبغى أستبدله|المنتج اللي)")
TASKVERB = re.compile(r"^(لخّص|لخص|أعد|حوّل|حول|صنّف|صنف|خلّ|هل هذي|هل هذه|استلمت|كان عندك|اكتب|صحح|صحّح|استخرج|طلّع|انقل|أوجز|اختصر)")
KEEP_PY = {1379, 1380, 1381, 1383, 1385, 1387, 1388, 1393, 1395, 1402, 1413, 1414, 1418, 1419, 1420, 1424, 1406, 1407}
NO_FILLER = re.compile(r"يوضح النص الفكرة الرئيسة بإيجاز")

def main():
    train = load(os.path.join(ROOT, "sft_train.jsonl"))
    log("المرحلة 2: بدء تنظيف train (%d صفًا أصليًا)" % len(train))
    ref_q = set(norm(q) for q, a in refusal_rows())
    ref_family_idx = set(range(700, 850))
    kept = []        # (row_dict, source)
    review = []      # dicts
    dropped = []     # dicts
    def drop(i, r, why): dropped.append({"source_index": i, "reason": why, "question": Q(r), "answer": A(r)})
    def rev(i, r, why, ans=None): review.append({"messages": [{"role": "user", "content": Q(r)}, {"role": "assistant", "content": ans or A(r)}],
                                                 "meta": {"type": task_type(Q(r), A(r)), "region": "none"}, "review_reason": why, "source_index": i})
    compare_first = {}
    for i, r in enumerate(train):
        q, a = Q(r), A(r)
        if NON_SAUDI_RE.search(q) or NON_SAUDI_RE.search(a):
            drop(i, r, "مؤشر غير سعودي في السؤال («شو»)"); continue
        if "ثانياً، يختلفان في الوظيفة" in a:
            compare_first.setdefault(a, []).append((i, q)); continue      # يُعالج أدناه
        if re.search(r"(في بايثون|لغة بايثون|لبايثون)", q) and not q.startswith("لخّص"):
            if i in KEEP_PY:
                kept.append((row(q, a, "python"), i))
            else:
                drop(i, r, "بايثون: مصطلحات مترجمة/مخترعة؛ استُبدل بصفوف كود صحيحة");
            continue
        if "\nالنص:" in q:
            drop(i, r, "عائلة الاستخراج: الإجابة لا تطابق المهمة؛ أُعيد بناؤها من جدول يدوي"); continue
        if i in FACT_REVIEW:
            rev(i, r, FACT_REVIEW[i]); continue
        if i in FACT_FIXES:
            a = FACT_FIXES[i]
        first = q.split("\n")[0]
        if "\n" in q and re.search(r"(لخص|أوجز|خلاصة|الفكرة)", first):
            if NO_FILLER.search(a):
                drop(i, r, "تلخيص بنقاط فيها حشو فارغ"); continue
        if i in ref_family_idx or (task_type(q, a) == "refusal" and norm(q) in ref_q):
            drop(i, r, "رفض قديم؛ استُبدل بجدول الرفض الجديد المتنوع الصياغة"); continue
        if 2212 <= i <= 2241:
            rev(i, r, "رفض تحويل تاريخ هجري/ميلادي بإجابة عامية؛ الرفض هنا غير مطلوب ويحتاج قرارًا"); continue
        if task_type(q, a) == "refusal" or REFUSAL_START.search(a[:40]):
            if norm(q) in ref_q: drop(i, r, "رفض قديم؛ استُبدل"); continue
        if "حالة طلب الصيانة رقم" in q:
            drop(i, r, "يخترع حالة طلب صيانة (مطلوب حذفه صراحة)"); continue
        if CUSTOMER.search(q) and "صاحبي" not in q and not TASKVERB.match(q) and "أجب بإيجاز" not in q:
            rev(i, r, "يخترع حالة/سياسة/إجراء لجهة مجهولة"); continue
        if DIALECT_ANS_RE.search(a):
            rev(i, r, "مؤشرات لهجة في إجابة يفترض أن تكون بالفصحى: " + DIALECT_ANS_RE.search(a).group(0)); continue
        if wc(a) > 60 and not re.search(r"\n|[-•\d]\.", a):
            rev(i, r, "إجابة أطول من 60 كلمة"); continue
        typ = task_type(q, a)
        typ = {"other": "informational"}.get(typ, typ)
        region = "saudi_general" if DIALECT_ANS_RE.search(q) else "none"
        kept.append((row(q, a, typ, region), i))
    # ---- compare
    n_cmp = 0
    for a, lst in compare_first.items():
        first_idx = lst[0][0]
        first_sentence = a.replace(" ثانياً، يختلفان في الوظيفة أو طريقة الاستخدام بحسب السياق.", "")
        second = COMPARE_SECOND[first_idx]
        new_a = first_sentence + " " + second
        qs = [q for i, q in lst if "نقاط" not in q]        # صياغة «نقاط موجزة» لا تناسب إجابة فقرة
        for k in pick_diverse(qs, 3):
            kept.append((row(qs[k], new_a, "compare"), lst[0][0])); n_cmp += 1
        for i, q in lst:
            if q not in [qs[k] for k in pick_diverse(qs, 3)]:
                dropped.append({"source_index": i, "reason": "زيادة على 3 صياغات للإجابة نفسها (احتُفظ بالأكثر تنوعًا)", "question": q, "answer": a})
    log("المرحلة 2: مقارنات أُعيدت كتابتها: %d صفًا من %d إجابة" % (n_cmp, len(compare_first)))
    # ---- extraction rebuilt
    n_ex = 0
    for ti, (text, tasks) in enumerate(EXTRACT_TEXTS):
        for ki, (task, ans) in enumerate(tasks):
            frame = EXTRACT_FRAMES[(ti + ki) % len(EXTRACT_FRAMES)]
            q = frame.format(t=task, x=text)
            kept.append((row(q, ans, "extract"), -1)); n_ex += 1
    log("المرحلة 2: صفوف استخراج مبنية يدويًا: %d" % n_ex)
    # ---- python
    n_py = 0
    for q, a in python_rows():
        kept.append((row(q, a, "python"), -1)); n_py += 1
    log("المرحلة 2: صفوف بايثون جديدة: %d" % n_py)
    # ---- refusals
    n_rf = 0
    for q, a in refusal_rows():
        reg = "saudi_general" if DIALECT_ANS_RE.search(q) else "none"
        kept.append((row(q, a, "refusal", reg), -1)); n_rf += 1
    log("المرحلة 2: صفوف رفض جديدة: %d" % n_rf)
    # ---- سقف 3 صياغات لكل إجابة
    groups = collections.OrderedDict()
    for rw, src in kept:
        groups.setdefault(rw["messages"][1]["content"], []).append((rw, src))
    final = []
    for a, lst in groups.items():
        if len(lst) <= 3:
            final += [x[0] for x in lst]
        else:
            qs = [x[0]["messages"][0]["content"] for x in lst]
            ch = pick_diverse(qs, 3)
            final += [lst[k][0] for k in ch]
            for k in range(len(lst)):
                if k not in ch:
                    dropped.append({"source_index": lst[k][1], "reason": "زيادة على 3 صياغات للإجابة نفسها", "question": qs[k], "answer": a})
    # سقف 3 يشمل الأسئلة المكررة أيضًا
    seen_q = set(); uniq = []
    for rw in final:
        k = norm(rw["messages"][0]["content"])
        if k in seen_q: continue
        seen_q.add(k); uniq.append(rw)
    w = BatchWriter(os.path.join(OUT, "train_part_base.jsonl"), "train_base")
    for rw in uniq: w.add(rw)
    w.close()
    for name, data in (("train_review.jsonl", review), ("train_dropped.jsonl", dropped)):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            for d in data: f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print("kept", len(uniq), "review", len(review), "dropped", len(dropped))
    log("المرحلة 2: الجزء الأساسي %d صفًا، للمراجعة %d، محذوف %d" % (len(uniq), len(review), len(dropped)))
    c = collections.Counter(r["meta"]["type"] for r in uniq); print(c)
    c = collections.Counter(d["reason"][:40] for d in dropped); print(c.most_common(12))
    c = collections.Counter(d["review_reason"][:40] for d in review); print(c.most_common(12))

if __name__ == "__main__":
    main()
