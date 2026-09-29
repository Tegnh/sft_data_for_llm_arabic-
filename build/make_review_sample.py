# -*- coding: utf-8 -*-
"""review_sample.md: 30 صفًا عشوائيًا من كل منطقة (من sft_train_v2.jsonl) للمراجعة اليدوية."""
import os, sys, random
sys.path.insert(0, os.path.dirname(__file__))
from common import *
NAMES = {"nejd": "نجد (الرياض، القصيم، حائل)", "hijaz": "الحجاز (جدة، مكة، المدينة)", "south": "الجنوب (عسير، جازان، نجران، الباحة)",
         "east": "الشرقية (الدمام، الأحساء، القطيف)", "north": "الشمال (تبوك، الجوف، الحدود الشمالية)"}
TYPES = {"informational": "معلوماتي", "advice": "نصيحة", "summarize": "تلخيص رسالة", "extract": "استخراج من رسالة", "rewrite": "إعادة صياغة بالفصحى", "refusal": "رفض"}
rows = load(os.path.join(ROOT, "sft_train_v2.jsonl"))
rng = random.Random(2026)
out = ["# عينة المراجعة اليدوية (30 صفًا لكل منطقة)", "",
       "صفوف عشوائية (بذرة ثابتة) من صفوف اللهجات في `sft_train_v2.jsonl`. لكل صف افحص:", "",
       "- **اللهجة**: هل تُقال هذه المفردات فعلًا في المنطقة؟ (استعملت مفردات سعودية عامة أو ما أنا متأكد منه، فالفروق بين المناطق محدودة عمدًا).",
       "- **المطابقة**: هل معنى السؤال يطابق الإجابة تمامًا؟",
       "- **الفصحى**: هل الإجابة فصحى مبسطة بلا عامية؟", ""]
for reg in ["nejd", "hijaz", "south", "east", "north"]:
    cand = [r for r in rows if r["meta"]["region"] == reg and r["meta"]["type"] in TYPES]
    out += ["## " + NAMES[reg], "", "| # | النوع | سؤال المستخدم | إجابة المساعد | ملاحظتك |", "|---|---|---|---|---|"]
    for i, r in enumerate(rng.sample(cand, 30), 1):
        q = r["messages"][0]["content"].replace("|", "\\|").replace("\n", "<br>")
        a = r["messages"][1]["content"].replace("|", "\\|").replace("\n", "<br>")
        out.append("| %d | %s | %s | %s |  |" % (i, TYPES[r["meta"]["type"]], q, a))
    out.append("")
open(os.path.join(ROOT, "review_sample.md"), "w", encoding="utf-8").write("\n".join(out))
log("review_sample.md: كُتبت 150 صفًا (30 × 5 مناطق)")
