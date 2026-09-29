# -*- coding: utf-8 -*-
"""المرحلة 1: تدقيق sft_train.jsonl و sft_val.jsonl قبل أي تعديل. يقرأ فقط ويكتب audit_report.md."""
import collections, re, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

train = load(os.path.join(ROOT, "sft_train.jsonl"))
val = load(os.path.join(ROOT, "sft_val.jsonl"))
A = lambda r: r["messages"][-1]["content"]
Q = lambda r: r["messages"][-2]["content"]

INVENTED_PY = ["طريقة الفرقعة", "كلمة طالما", "حلقة طالما", "كلمة لكل", "حلقة لكل", "دالة المبتدئ", "كلمة حذف", "كلمة إرجاع",
               "كلمة استيراد", "كلمة الإنتاج", "كلمة كسر", "كلمة إذا", "كلمة وإلا", "كلمة مع", "كلمة باسم", "علامة الشباك",
               "الكلمة المفتاحية الخاصة", "الطريقة الخاصة بالإضافة", "كتلة المحاولة", "كتلة الالتقاط", "طريقة الإزالة",
               "طريقة الربط", "طريقة التمديد", "الدالة المدمجة الخاصة", "دالة النطاق", "دالة الفتح", "دالة التصفية",
               "طريقة التقسيم", "دالة الطول", "دالة النوع", "الذات", "دالة المبتدئ", "كلمة صنف", "كلمة الفتح", "بامتداد باي"]

def analyse(rows, name):
    d = {}
    d["rows"] = len(rows)
    d["system"] = sum(1 for r in rows if r["messages"][0]["role"] == "system")
    ans = collections.defaultdict(list)
    for r in rows: ans[A(r)].append(r)
    d["unique_answers"] = len(ans)
    dups = {a: v for a, v in ans.items() if len(v) > 1}
    d["dup_groups"] = len(dups)
    d["dup_rows"] = sum(len(v) for v in dups.values())
    d["dup_dist"] = collections.Counter(len(v) for v in dups.values())
    d["over3_groups"] = sum(1 for v in dups.values() if len(v) > 3)
    d["over3_excess"] = sum(len(v) - 3 for v in dups.values() if len(v) > 3)
    d["after_cap3"] = sum(min(3, len(v)) for v in ans.values())
    d["phrase_ctx"] = sum(1 for r in rows if "بحسب السياق" in A(r))
    d["phrase_exact"] = sum(1 for r in rows if "ثانياً، يختلفان في الوظيفة أو طريقة الاستخدام بحسب السياق." in A(r))
    py = [r for r in rows if "بايثون" in Q(r) or "بايثون" in A(r)]
    d["py_rows"] = len(py)
    d["py_invented"] = [r for r in py if any(t in A(r) for t in INVENTED_PY)]
    d["dialect_ans"] = [r for r in rows if DIALECT_ANS_RE.search(A(r))]
    d["nonsaudi_any"] = [r for r in rows if NON_SAUDI_RE.search(Q(r)) or NON_SAUDI_RE.search(A(r))]
    d["types"] = collections.Counter(task_type(Q(r), A(r)) for r in rows)
    paras = set(); para_use = collections.Counter()
    for r in rows:
        q = Q(r)
        if "\n" in q:
            p = norm(q.split("\n", 1)[1]); paras.add(p); para_use[p] += 1
    d["paras"] = len(paras)
    d["para_max_use"] = max(para_use.values()) if para_use else 0
    d["long"] = sum(1 for r in rows if wc(A(r)) > 60)
    d["uq"] = len(set(Q(r) for r in rows))
    return d

def fmt_counter(c): return "، ".join("%s: %d" % (k, v) for k, v in sorted(c.items(), key=lambda x: -x[1]))

# مشاكل إضافية اكتُشفت أثناء الفحص
tmpl_texts = [r for r in train if "\nالنص:" in Q(r)]
filler_bullets = [r for r in train if "يوضح النص الفكرة الرئيسة بإيجاز" in A(r)]
maint = [r for r in train if "حالة طلب الصيانة" in Q(r)]
overlap_q = set(norm(Q(r)) for r in train) & set(norm(Q(r)) for r in val)
overlap_a = set(norm(A(r)) for r in train) & set(norm(A(r)) for r in val)
tp = set(); vp = set()
for rs, s in ((train, tp), (val, vp)):
    for r in rs:
        if "\n" in Q(r): s.add(norm(Q(r).split("\n", 1)[1]))

out = ["# تقرير التدقيق (المرحلة 1)", "",
       "> أُنتج تلقائيًا بالسكربت `build/audit.py` من الملفين الأصليين دون تعديلهما. الأرقام أدناه هي ما قبل أي تنظيف.", ""]
for name, rows in (("sft_train.jsonl", train), ("sft_val.jsonl", val)):
    d = analyse(rows, name)
    out += ["## %s" % name, "",
            "| المقياس | القيمة |", "|---|---|",
            "| عدد الصفوف | %d |" % d["rows"],
            "| صفوف فيها رسالة system | %d |" % d["system"],
            "| أسئلة فريدة | %d |" % d["uq"],
            "| إجابات فريدة | %d |" % d["unique_answers"],
            "| إجابات مكررة (مجموعات) | %d |" % d["dup_groups"],
            "| صفوف داخل الإجابات المكررة | %d |" % d["dup_rows"],
            "| توزيع عدد الصياغات لكل إجابة مكررة | %s |" % ("، ".join("%d صياغات × %d إجابة" % (k, v) for k, v in sorted(d["dup_dist"].items()))),
            "| إجابات تتجاوز 3 صياغات (مجموعات / صفوف زائدة) | %d / %d |" % (d["over3_groups"], d["over3_excess"]),
            "| الصفوف المتبقية لو طُبّق حد 3 صياغات فقط | %d |" % d["after_cap3"],
            "| صفوف فيها عبارة «بحسب السياق» | %d |" % d["phrase_ctx"],
            "| منها الجملة الفارغة «ثانياً، يختلفان في الوظيفة أو طريقة الاستخدام بحسب السياق.» | %d |" % d["phrase_exact"],
            "| صفوف بايثون (السؤال أو الإجابة) | %d |" % d["py_rows"],
            "| صفوف بايثون بمصطلحات مخترعة/مترجمة حرفيًا للكلمات المفتاحية | %d |" % len(d["py_invented"]),
            "| صفوف فيها مؤشرات لهجة في الإجابة | %d |" % len(d["dialect_ans"]),
            "| صفوف فيها مؤشرات غير سعودية (كده، عايز، شو…) | %d |" % len(d["nonsaudi_any"]),
            "| إجابات أطول من 60 كلمة | %d |" % d["long"],
            "| فقرات فريدة (أسئلة متعددة الأسطر، بعد التطبيع) | %d (أقصى استعمال للفقرة الواحدة: %d) |" % (d["paras"], d["para_max_use"]),
            "", "**توزيع أنواع المهام (تصنيف تقريبي بالقواعد):** " + fmt_counter(d["types"]), ""]
    if name == "sft_train.jsonl":
        out += ["أمثلة على مصطلحات بايثون المخترعة في الإجابات:", ""]
        for r in d["py_invented"][:6]:
            out.append("- س: %s ← ج: %s" % (Q(r), A(r)[:120]))
        out.append("")

out += ["## مشاكل إضافية لم تُذكر في المهمة (وجدتها أثناء الفحص)", "",
        "1. **عائلة الاستخراج مختلة الوسم:** %d صفًا من قالب «استخرج…/صنف النبرة» (8 مهام × 25 نصًا، كل نص مكرر 8 مرات). الإجابة ثابتة لكل نص وتصلح لمهمة واحدة فقط، فتظهر مثلًا «استخرج التواريخ» ← «المهندس فهد»، و«صنف النبرة» ← «سامر». هذه أخطاء تعليمية مباشرة." % len(tmpl_texts),
        "2. **حشو في التلخيص بثلاث نقاط:** %d إجابة فيها البندان الفارغان «يوضح النص الفكرة الرئيسة بإيجاز» و«يركز على الأثر أو الفائدة المذكورة»." % len(filler_bullets),
        "3. **صفوف يخترع فيها المساعد حالة/سياسة/إجراء لجهة مجهولة** (حالة طلب، شحنة، استرداد خلال 3–5 أيام، شكاوى…): صف الصيانة (%d) وعشرات الصفوف المشابهة." % len(maint),
        "4. **إجابات عامية في صفوف كان يجب أن تكون بالفصحى** (وش، أبغى، بيتم، زي…): انظر رقم «مؤشرات لهجة في الإجابة» أعلاه.",
        "5. **أخطاء وقائع:** برج خليفة «أكثر من 880 مترًا» (الصحيح 828 م تقريبًا)، «أطول حيوان في العالم هو الحوت الأزرق» (غير دقيق)، «يصبح نهر الغانج» (خطأ إملائي)، إجابة قمم الجبال فيها تكرار لإفرست، «أكبر مدينة في سوريا حلب» (خلافية)، تاريخ معركة القادسية (خلاف بين 14 و15 هـ).",
        "6. **رفض حي بصيغ نمطية:** 50 موضوع رفض × 6 أسئلة بصياغات آلية («أجب بإيجاز / اذكر حدود إجابتك / أجب بدقة…») والإجابة نفسها 6 مرات.",
        "7. **التداخل بين train و val:** أسئلة مشتركة (بعد التطبيع) = %d، إجابات مشتركة = %d، فقرات مشتركة = %d. يجب ألا يتشارك الملفان شيئًا في v2." % (len(overlap_q), len(overlap_a), len(tp & vp)),
        "8. **السكربتات المذكورة** (`generate_sft.py`, `merge_sft.py`, `build_final_sft.py`, `clean_dataset.py`) و`sft_current_backup.jsonl` **غير موجودة في المستودع** (فيه الملفان الأصليان فقط)، فكتبت سكربتات جديدة في `build/`.",
        ""]
open(os.path.join(ROOT, "audit_report.md"), "w", encoding="utf-8").write("\n".join(out))
log("المرحلة 1: كُتب audit_report.md (لم يُعدَّل أي ملف أصلي)")
print("\n".join(out))
