# -*- coding: utf-8 -*-
"""يبني أسطر mk_batch (mode new) من ملفات الفقرات والأسئلة.
الاستعمال: build_grounded.py para1.txt qa1.txt [--multi] > out.txt
"""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
paras = {}
for f in sys.argv[1].split(","):
    for line in open(os.path.join(L.V3, "gsrc", f), encoding="utf-8"):
        if "¦" in line:
            k, t = [x.strip() for x in line.split("¦", 1)]
            paras[k] = t
use = collections.Counter()
for f in sys.argv[2].split(","):
    for line in open(os.path.join(L.V3, "gsrc", f), encoding="utf-8"):
        line = line.rstrip("\n")
        if "¦" not in line: continue
        p = [x.strip() for x in line.split("¦")]
        pid, typ, reg, split, tpl = p[:5]
        P = paras[pid]; use[(pid, split)] += 1
        turns = [tpl.replace("{P}", P)]
        if typ == "multi_turn": turns += [p[5], p[6], p[7]]
        else: turns.append(p[5])
        print(f"{typ} ¦ {reg} ¦ {split} ¦ " + "|||".join(t.replace("\n", "⏎") for t in turns))
bad = [(k, v) for k, v in use.items() if v > 3]
if bad: print("# فقرة مستعملة أكثر من 3:", bad, file=sys.stderr)
