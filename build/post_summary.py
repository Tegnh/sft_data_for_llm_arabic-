# -*- coding: utf-8 -*-
"""يُلحق بـ audit_report.md أرقام ما بعد التنظيف."""
import os, sys, collections
sys.path.insert(0, os.path.dirname(__file__))
from common import *
tr = load(os.path.join(ROOT, "sft_train_v2.jsonl")); va = load(os.path.join(ROOT, "sft_val_v2.jsonl")); te = load(os.path.join(ROOT, "sft_dialect_test.jsonl"))
rv = load(os.path.join(ROOT, "needs_review.jsonl")); dr = load(os.path.join(ROOT, "build", "out", "train_dropped.jsonl"))
A = lambda r: r["messages"][1]["content"]
ans = collections.Counter(A(r) for r in tr)
rp = os.path.join(ROOT, "audit_report.md"); s = open(rp, encoding="utf-8").read()
if "## ما بعد التنظيف" in s: s = s[:s.index("## ما بعد التنظيف")].rstrip() + "\n\n"
cnt = lambda rows, f: collections.Counter(f(r) for r in rows)
L = ["## ما بعد التنظيف (الملفات النهائية)", "", "| المقياس | القيمة |", "|---|---|",
     "| sft_train_v2 — صفوف | %d |" % len(tr), "| sft_train_v2 — إجابات فريدة | %d |" % len(ans),
     "| أكثر تكرار لإجابة في train (الحد 3) | %d |" % max(ans.values()),
     "| sft_val_v2 — صفوف / إجابات فريدة | %d / %d |" % (len(va), len(set(A(r) for r in va))),
     "| sft_dialect_test — عناصر | %d |" % len(te), "| needs_review — صفوف | %d |" % len(rv),
     "| صفوف الأصل المحذوفة من train | %d |" % len(dr), "", "**أسباب دخول الصفوف إلى needs_review:**", ""]
for k, v in cnt(rv, lambda r: r["review_reason"].split(":")[0][:70]).most_common(): L.append("- %s: %d" % (k, v))
L += ["", "**أسباب حذف صفوف الأصل من train:**", ""]
for k, v in cnt(dr, lambda r: r["reason"][:70]).most_common(): L.append("- %s: %d" % (k, v))
L += ["", "**أنواع المهام في train v2:** " + "، ".join("%s: %d" % kv for kv in cnt(tr, lambda r: r["meta"]["type"]).most_common()),
      "", "**المناطق في train v2:** " + "، ".join("%s: %d" % kv for kv in cnt(tr, lambda r: r["meta"]["region"]).most_common()), ""]
open(rp, "w", encoding="utf-8").write(s + "\n".join(L))
log("audit_report.md: أُلحق قسم ما بعد التنظيف")
