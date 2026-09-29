# -*- coding: utf-8 -*-
"""دمج أجزاء train النهائية -> sft_train_v2.jsonl و needs_review.jsonl (يُشغَّل بعد clean_train / gen_dialect / gen_pairs)."""
import os, sys, json, random, collections
sys.path.insert(0, os.path.dirname(__file__))
from common import *

OUT = os.path.join(ROOT, "build", "out")
def main():
    base = load(os.path.join(OUT, "train_part_base.jsonl"))
    dia = load(os.path.join(OUT, "dialect_train.jsonl"))
    pairs = load(os.path.join(OUT, "pairs_train.jsonl"))
    allrows = dia + pairs + base            # الأولوية للصفوف الجديدة عند تجاوز سقف الإجابة
    ans = collections.Counter(); seenq = set(); kept = []; over = []
    for r in allrows:
        q, a = r["messages"][0]["content"], r["messages"][1]["content"]
        kq = norm(q)
        if kq in seenq: over.append(("سؤال مكرر", r)); continue
        if ans[norm(a)] >= 3: over.append(("إجابة تتجاوز 3 صياغات", r)); continue
        seenq.add(kq); ans[norm(a)] += 1; kept.append(r)
    random.Random(42).shuffle(kept)
    w = BatchWriter(os.path.join(ROOT, "sft_train_v2.jsonl"), "sft_train_v2")
    for r in kept: w.add(r)
    w.close()
    log("assemble: أُسقط %d صفًا عند الدمج بسبب %s" % (len(over), dict(collections.Counter(x[0] for x in over))))
    # needs_review: من التنظيف + أي شيء آخر يُضاف لاحقًا
    rev_all = load(os.path.join(OUT, "train_review.jsonl"))
    train_q = set(norm(r["messages"][0]["content"]) for r in kept)
    rev = [r for r in rev_all if norm(r["messages"][0]["content"]) not in train_q]     # ما استُبدل بصيغة سليمة في train لا يحتاج مراجعة
    log("assemble: %d صفًا في المراجعة استُبدلت أسئلتها بصيغة سليمة داخل train فأُخرجت من needs_review" % (len(rev_all) - len(rev)))
    with open(os.path.join(ROOT, "needs_review.jsonl"), "w", encoding="utf-8") as f:
        for r in rev: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log("assemble: needs_review.jsonl = %d صفًا" % len(rev))
    print("train_v2", len(kept), "dropped-at-merge", len(over), collections.Counter(x[0] for x in over))
    ref = sum(1 for r in kept if r["meta"]["type"] in ("refusal", "text_unanswerable"))
    print("refusal ratio", ref, ref / len(kept))
    print(collections.Counter(r["meta"]["type"] for r in kept))
    print(collections.Counter(r["meta"]["region"] for r in kept))
if __name__ == "__main__":
    main()
