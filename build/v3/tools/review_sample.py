# -*- coding: utf-8 -*-
"""ينتج build/v3/review_sample.md: عينة عشوائية بذرة 42 — 30/منطقة من train، 20/منطقة من val، 30 من practical-messages، 20 من practical-grounded."""
import sys, os, random, collections
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
tr = L.load_jsonl(os.path.join(L.V3, "sft_train_v3.jsonl")); va = L.load_jsonl(os.path.join(L.V3, "sft_val_v3.jsonl"))
rng = random.Random(42)
def esc(s): return s.replace("|", "\\|").replace("\n", "<br>")
def cell(r):
    m = r["messages"]
    if len(m) == 2: return esc(m[0]["content"]), esc(m[1]["content"])
    return esc("<br>".join(("👤 " if x["role"] == "user" else "🤖 ") + x["content"] for x in m[0::2] if False)) or "", ""
def render(r):
    m = r["messages"]
    if len(m) == 2: return esc(m[0]["content"]), esc(m[1]["content"])
    q = "<br>".join(f"**م{i//2+1}:** {esc(m[i]['content'])}" for i in range(0, len(m), 2))
    a = "<br>".join(f"**ج{i//2+1}:** {esc(m[i]['content'])}" for i in range(1, len(m), 2))
    return q, a
out = ["# عينة المراجعة النهائية (v3)\n",
       "> سُحبت بذرة ثابتة 42. عمود «ملاحظتك» فارغ عمدًا لتكتب فيه مراجعتك النهائية (اللهجة الأصيلة، صحة الحقائق، مطابقة الإجابة). المعجم مسودة لم تُراجَع لغويًا.\n"]
def section(title, rows):
    out.append(f"\n## {title} ({len(rows)} صفًا)\n\n| # | النوع | المنطقة | السؤال | الإجابة | ملاحظتك |\n|---|---|---|---|---|---|\n")
    for i, r in enumerate(rows, 1):
        q, a = render(r); out.append(f"| {i} | {r['meta']['type']} | {r['meta']['region']} | {q} | {a} |  |\n")
for g in L.REGIONS:
    pool = [r for r in tr if r["meta"]["region"] == g]; section(f"train — {g}", rng.sample(pool, 30))
for g in L.REGIONS:
    pool = [r for r in va if r["meta"]["region"] == g]; section(f"val — {g}", rng.sample(pool, min(20, len(pool))))
pm = [r for r in tr + va if r["meta"]["source"] == "v3-practical-messages"]; section("practical-messages", rng.sample(pm, 30))
pg = [r for r in tr + va if r["meta"]["source"] == "v3-practical-grounded"]; section("practical-grounded", rng.sample(pg, 20))
open(os.path.join(L.V3, "review_sample.md"), "w", encoding="utf-8").write("".join(out))
print("review_sample.md:", sum(o.count("\n| ") for o in out) - 0, "أسطر جدول تقريبًا")
