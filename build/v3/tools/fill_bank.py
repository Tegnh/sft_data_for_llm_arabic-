# -*- coding: utf-8 -*-
"""يملأ مهام new_topic وصفوف اللهجة الجديدة من بنك الأسئلة build/v3/bank/*.txt مع إطار لهجي حسب المنطقة.
  fill_bank.py tasks <region> <n>                       -> سطور newtask
  fill_bank.py new <region> <split> <n> <mix> [tech%]   -> سطور new    (mix مثل informational:14,advice:10,...)
"""
import sys, os, re, glob, json, random
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
BANK = os.path.join(L.V3, "bank"); USED = os.path.join(BANK, "used.json")
W = r"(?<![ء-ي])%s(?![ء-ي])"
FR = {
 "nejd": {"subs": [], "pre": {"q": ["يالربع،", "جعلك سالم،", "دوبك سألني ولدي،", "توه أسأل نفسي،", "تراه ما فهمت،", "مب فاهم،", "مب متأكد،", "دوبك أفكر بالموضوع،"],
                               "t": ["يالربع،", "جعلك سالم،", "دوبك وصلتني،", "توه وصلتني،", "تراه محتاجها،"]}},
 "hijaz": {"subs": [("وش", "ايش"), ("ليش", "ليه"), ("وين", "فين")], "pre": {"q": ["معلش،", "لسه ما فهمت،", "برضو ما فهمت،", "معلش لسه محتار،"],
                               "t": ["معلش،", "وريني،", "لسه ما قريتها،", "معلش،"]}},
 "south": {"subs": [("وش", "ويش")], "pre": {"q": ["غادي أسأل،", "غادي أستفسر،", "ما شي عندي وقت أبحث،", "غادي أجرب أسأل هنا،"],
                               "t": ["ما شي عندي وقت،", "غادي أطلب مساعدتك،", "ما شي معي وقت،"]}},
 "east": {"subs": [("وش", "شنو"), ("أبغى", "أبا")], "pre": {"q": ["وايد محتار،", "أنطر ردك،", "هاي أول مرة أسأل،", "وايد أحتاج جوابك،"],
                               "t": ["وايد مشغول،", "أنطر ردك،", "وايد أحتاج مساعدتك،"]}},
 "north": {"subs": [("شلون", "أشلون")], "pre": {"q": ["حيل محتار،", "واجد محتار،", "وليدي يسأل،", "عقب الدوام أبغى أعرف،"],
                               "t": ["حيل مشغول،", "واجد مشغول،", "عقب الدوام أبغى أنهيها،"]}},
}
def load_bank():
    items = []
    for f in sorted(glob.glob(os.path.join(BANK, "*.txt"))):
        for i, line in enumerate(open(f, encoding="utf-8")):
            p = [x.strip() for x in line.rstrip("\n").split("¦")]
            if len(p) == 3 and p[0] in L.ALLOWED_TYPE: items.append({"key": f"{os.path.basename(f)}:{i}", "type": p[0], "q": p[1], "a": p[2]})
    return items
def used(): return set(json.load(open(USED))) if os.path.exists(USED) else set()
def save_used(s): json.dump(sorted(s), open(USED, "w"))
def frame(region, typ, q, k):
    cfg = FR[region]; kind = "t" if typ in ("summarize", "extract", "rewrite") else "q"
    lines = q.split("\n"); first = lines[0]
    for old, new in cfg["subs"]:
        if re.search(W % old, first):
            lines[0] = re.sub(W % old, new, first, count=1); return "\n".join(lines)
    opts = cfg["pre"][kind]; return opts[k % len(opts)] + " " + q
def take(items, u, typ, latin=None):
    for it in items:
        if it["key"] in u or it["type"] != typ: continue
        if latin is not None and bool(re.search("[A-Za-z]", it["q"])) != latin: continue
        u.add(it["key"]); return it
    return None
if __name__ == "__main__":
    mode, region = sys.argv[1], sys.argv[2]
    items = load_bank(); u = used(); k = random.Random(hash(region) % 1000).randint(0, 5)
    if mode == "tasks":
        n = int(sys.argv[3]); done = set()
        for f in glob.glob(os.path.join(L.V3, "parts", "*", "batch_*.jsonl")):
            for r in L.load_jsonl(f):
                if r.get("task_id"): done.add(r["task_id"])
        ts = [t for t in L.load_jsonl(os.path.join(L.V3, "assign", f"{region}.jsonl")) if t["reason"] == "new_topic" and t["task_id"] not in done][:n]
        for t in ts:
            typ = t["type"] if t["type"] in ("informational", "advice", "refusal", "extract", "summarize", "rewrite") else "informational"
            it = take(items, u, typ)
            if not it: print(f"# لا بنك كافٍ لنوع {typ} للمهمة {t['task_id']}", file=sys.stderr); continue
            k += 1; print(f"{t['task_id']} ¦ {typ} ¦ {frame(region, typ, it['q'], k).replace(chr(10), '⏎')} ¦ {it['a']}")
    else:
        split, n, mix = sys.argv[3], int(sys.argv[4]), sys.argv[5]; tech = float(sys.argv[6]) / 100 if len(sys.argv) > 6 else 0.2
        want = [(m.split(":")[0], int(m.split(":")[1])) for m in mix.split(",")]
        ntech = round(n * tech); tl = 0
        for typ, c in want:
            for _ in range(c):
                it = None
                if tl < ntech and typ in ("informational", "advice"): it = take(items, u, typ, latin=True)
                if it: tl += 1
                if not it: it = take(items, u, typ, latin=False if tl >= ntech else None)
                if not it: print(f"# لا بنك كافٍ لنوع {typ}", file=sys.stderr); continue
                k += 1; print(f"{typ} ¦ {region} ¦ {split} ¦ {frame(region, typ, it['q'], k).replace(chr(10), '⏎')}|||{it['a']}")
    save_used(u)
