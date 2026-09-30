# -*- coding: utf-8 -*-
"""يولّد سطور edit لمهام add_marker: استبدال كلمة السؤال في سطر التعليمة/السؤال ثم بادئة بديلة. الاستعمال: auto_edit.py <region> <lo> <hi> > file"""
import sys, os, re, glob
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
reg, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
CFG = {
 "south": {"subs": [(r"(?<![ء-ي])وش(?![ء-ي])", "ويش")],
           "pre": {"q": ["غادي أسأل،", "غادي أستفسر،", "ما شي عندي وقت أبحث،", "غادي أجرب أسأل هنا،"],
                   "t": ["ما شي عندي وقت،", "غادي أطلب مساعدتك،", "ما شي معي وقت،"],
                   "x": ["ما شي عندي وقت أقرأ،", "غادي أراجع النص،", "ما شي معي وقت أراجع،"]}},
 "east": {"subs": [(r"(?<![ء-ي])وش(?![ء-ي])", "شنو"), (r"(?<![ء-ي])أبغى(?![ء-ي])", "أبا")],
          "pre": {"q": ["وايد محتار،", "أنطر ردك،", "هاي أول مرة أسأل،", "وايد أحتاج جوابك،"],
                  "t": ["وايد مشغول،", "أنطر ردك،", "وايد أحتاج مساعدتك،"],
                  "x": ["وايد ما فهمت النص،", "أنطر ردك،", "وايد محتار،"]}},
 "north": {"subs": [(r"(?<![ء-ي])شلون(?![ء-ي])", "أشلون")],
           "pre": {"q": ["حيل محتار،", "واجد محتار،", "وليدي يسأل،", "عقب الدوام أبغى أعرف،"],
                   "t": ["حيل مشغول،", "واجد مشغول،", "عقب الدوام أبغى أنهيها،"],
                   "x": ["حيل ما فهمت النص،", "واجد ما فهمت النص،", "عقب الدوام أراجع النص،"]}},
}[reg]
rows = [r for r in L.load_jsonl(os.path.join(L.V3, "assign", f"{reg}.jsonl")) if r["reason"] == "add_marker"]
done = set()
for f in glob.glob(os.path.join(L.V3, "parts", "*", "batch_*.jsonl")):
    for r in L.load_jsonl(f):
        if r.get("task_id"): done.add(r["task_id"])
rows = [r for r in rows if r["task_id"] not in done][lo:hi]
k = 0
for r in rows:
    u = r["old"]["messages"][0]["content"]; lines = u.split("\n")
    kind = "x" if r["type"] in ("text_answerable", "text_unanswerable") else ("t" if r["type"] in ("summarize", "extract", "rewrite") else "q")
    if r["region"] == "saudi_general":
        print(f"{r['task_id']} ¦ ^ ¦ ياخي،"); continue
    # ابحث عن استبدال في السطر الأول (تعليمة/سؤال) ثم الأخير للنصوص
    cand = [0] if kind != "x" else [len(lines) - 1, 0]
    done_sub = False
    for ci in cand:
        for pat, new in CFG["subs"]:
            m = re.search(pat, lines[ci])
            if m:
                old = lines[ci]
                print(f"{r['task_id']} ¦ {old} ¦ {old[:m.start()] + new + old[m.end():]}"); done_sub = True; break
        if done_sub: break
    if not done_sub:
        opts = CFG["pre"][kind]; print(f"{r['task_id']} ¦ ^ ¦ {opts[k % len(opts)]}"); k += 1
