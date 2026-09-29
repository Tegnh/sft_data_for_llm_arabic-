# -*- coding: utf-8 -*-
"""المرحلة 3: توليد صفوف اللهجات السعودية (200 لكل منطقة) -> build/out/dialect_train.jsonl
سؤال المستخدم بلهجة المنطقة (واتساب)، وجواب المساعد بالفصحى المبسطة."""
import os, sys, random, re, json, collections
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from data_dialect_info import INFO
from data_dialect_advice import ADVICE
from data_dialect_msg import MSG
from data_dialect_ref import REFUSE

REGIONS = ["nejd", "hijaz", "south", "east", "north"]
LEX = {
 "nejd":  dict(w="وش",  y="ليش", h="شلون", n="الحين",  e="وين", s="أبغى", m="مين"),
 "hijaz": dict(w="ايش", y="ليه", h="كيف",  n="دحين",  e="وين", s="أبغى", m="مين"),
 "south": dict(w="وش",  y="ليش", h="كيف",  n="الحين", e="وين", s="أبغى", m="مين"),
 "east":  dict(w="وش",  y="ليش", h="شلون", n="هالحين", e="وين", s="أبغى", m="مين"),
 "north": dict(w="وش",  y="ليش", h="شلون", n="الحين", e="وين", s="أبغى", m="مين"),
}
OPEN = {
 "nejd": ["هلا والله", "مساك الله بالخير", "الله يحييك", "السلام عليكم", "هلا", "حياك الله"],
 "hijaz": ["يا هلا", "صباح الخير", "مساء الخير", "السلام عليكم", "الله يسعد صباحك"],
 "south": ["حياك الله", "السلام عليكم", "مرحبا", "هلا ومرحبا"],
 "east": ["هلا", "يا هلا", "السلام عليكم", "شلونك"],
 "north": ["هلا والله", "حياك الله", "السلام عليكم", "الله يحييك"],
}
CLOSE = {
 "nejd": ["تكفى", "الله يعافيك", "مشكور", "يعطيك العافية"],
 "hijaz": ["يعطيك العافية", "الله يعطيك العافية", "شكرًا"],
 "south": ["جزاك الله خير", "بارك الله فيك", "الله يجزاك خير"],
 "east": ["الله يعطيك العافية", "مشكور", "يعطيك العافية"],
 "north": ["الله يعافيك", "مشكور", "شكرًا"],
}
CITIES = {
 "nejd": ["الرياض", "بريدة", "عنيزة", "حائل", "الرس"],
 "hijaz": ["جدة", "مكة", "المدينة", "الطائف", "ينبع"],
 "south": ["أبها", "خميس مشيط", "جازان", "نجران", "الباحة"],
 "east": ["الدمام", "الخبر", "الأحساء", "القطيف", "الجبيل"],
 "north": ["تبوك", "سكاكا", "عرعر", "طريف", "القريات"],
}
CITY_PREFIX = ["أنا في {c}، ", "أنا ساكن في {c}، ", "هنا في {c}، ", "من {c}، "]
SUM_F = ["لخص لي هالرسالة:\n{msg}", "اختصر لي هالرسالة بجملة وحدة:\n{msg}", "{w} خلاصة هالرسالة؟\n{msg}", "{msg}\n\nلخص لي الكلام هذا", "لخّص لي رسالة وصلتني:\n{msg}"]
EXT_F = ["طلّع لي {item} من هالرسالة:\n{msg}", "{msg}\n\n{w} {item} اللي فيها؟", "استخرج لي {item} من الرسالة هذي:\n{msg}", "{s} {item} بس من هالرسالة:\n{msg}"]
REW_F = ["اكتب لي هالرسالة بالفصحى:\n{msg}", "حوّل كلامي هذا لفصحى مبسطة:\n{msg}", "{msg}\n\nصيغها لي بالفصحى لو سمحت", "أعد صياغة هالرسالة بأسلوب فصيح:\n{msg}", "{s} هالجملة بالفصحى:\n{msg}"]

def sub(text, region):
    for k, v in LEX[region].items():
        text = text.replace("{%s}" % k, v)
    return text

def decorate(text, region, rng, allow_city=True):
    t = re.sub(r"(?<!،) (كيف|شلون)$", r"، \1", text)
    if allow_city and rng.random() < 0.28:
        t = rng.choice(CITY_PREFIX).format(c=rng.choice(CITIES[region])) + t
    if rng.random() < 0.40:
        t = rng.choice(OPEN[region]) + "، " + t
    if rng.random() < 0.33:
        t = t.rstrip("؟?.،") + (" " if rng.random() < .5 else "، ") + rng.choice(CLOSE[region])
    return t

def build_cores():
    cores = []
    for c in INFO:   cores.append(dict(kind="info", type="informational", v=list(c[:3]), a=c[3]))
    for c in ADVICE: cores.append(dict(kind="advice", type="advice", v=list(c[:3]), a=c[3]))
    for c in MSG:
        if c[0] == "ext": cores.append(dict(kind="msg", type="extract", v=list(c[2]), a=c[3], item=c[1]))
        elif c[0] == "sum": cores.append(dict(kind="msg", type="summarize", v=list(c[1]), a=c[2]))
        else: cores.append(dict(kind="msg", type="rewrite", v=list(c[1]), a=c[2]))
    for c in REFUSE: cores.append(dict(kind="ref", type="refusal", v=list(c[:3]), a=c[3]))
    return cores

def generate(seed=20260929, per_region=200):
    rng = random.Random(seed)
    cores = build_cores()
    rng.shuffle(cores)
    cnt = collections.Counter(); tcnt = collections.Counter()
    rows = []; frame_i = collections.Counter()
    for core in cores:
        # اختر 3 مناطق الأقل امتلاء (مع كسر التعادل بالنوع ثم عشوائيًا)
        order = sorted(REGIONS, key=lambda r: (cnt[r], tcnt[(r, core["type"])], rng.random()))
        chosen = [r for r in order if cnt[r] < per_region][:3]
        rng.shuffle(chosen)
        for j, region in enumerate(chosen):
            v = core["v"][j]
            if core["kind"] == "msg":
                m = sub(v, region)
                fr = {"summarize": SUM_F, "extract": EXT_F, "rewrite": REW_F}[core["type"]]
                f = fr[frame_i[core["type"]] % len(fr)]; frame_i[core["type"]] += 1
                q = sub(f, region).replace("{msg}", m).replace("{item}", core.get("item", ""))
                q = q.replace("\n\n", "\n\n")
                q = decorate(q, region, rng, allow_city=False) if False else q
            else:
                q = decorate(sub(v, region), region, rng, allow_city=True)
            if not DIA_Q.search(q) and core["kind"] != "msg":   # سؤال بلا أي مؤشر لهجي: أضف جزيئة سعودية شائعة
                q = rng.choice(["ياخي", "والله", "يا شيخ"]) + " " + q
            rows.append(row(q, core["a"], core["type"], region))
            cnt[region] += 1; tcnt[(region, core["type"])] += 1
    return rows

MIXMAP = [("كلمة المرور", "الـ password"), ("الباسورد", "الـ password"), ("التطبيق", "الـ app"), ("الإيميل", "الـ email"),
          ("البريد الإلكتروني", "الـ email"), ("النسخ الاحتياطي", "الـ backup"), ("الواي فاي", "الـ Wi-Fi"), ("الواتساب", "الـ WhatsApp"),
          ("الواتس", "الـ WhatsApp"), ("التحديث", "الـ update"), ("الرابط", "الـ link"), ("اللابتوب", "الـ laptop"), ("الجروب", "الـ group"),
          ("الاجتماع", "الـ meeting"), ("الشاشة", "الـ screen"), ("الإنترنت", "الـ internet"), ("الفيروس", "الـ virus"),
          ("الموقع الإلكتروني", "الـ website"), ("الملف", "الـ file"), ("الصورة", "الـ photo"), ("الفاتورة", "الـ invoice"),
          ("الحساب", "الـ account"), ("الجوال", "الـ mobile"), ("الطابعة", "الـ printer"), ("المشروع", "الـ project"),
          ("التقرير", "الـ report"), ("الموعد", "الـ appointment"), ("المكتب", "الـ office"), ("الاشتراك", "الـ subscription")]

def mix_english(rows, rng, target=0.15):
    """خلط مصطلحات تقنية إنجليزية كما يفعل المتحدثون: استبدال مفردة تقنية واحدة في سؤال المستخدم فقط."""
    have = [r for r in rows if re.search("[A-Za-z]", r["messages"][0]["content"])]
    need = int(round(target * len(rows))) - len(have)
    cands = []
    for i, r in enumerate(rows):
        q = r["messages"][0]["content"]
        if re.search("[A-Za-z]", q): continue
        hits = [(a, b) for a, b in MIXMAP if a in q]
        if hits: cands.append((i, hits))
    rng.shuffle(cands)
    done = 0
    for i, hits in cands:
        if done >= need: break
        a, b = hits[0]
        q = rows[i]["messages"][0]["content"]
        rows[i]["messages"][0]["content"] = q.replace(a, b, 1)
        done += 1
    return len(cands), done

if __name__ == "__main__":
    log("المرحلة 3: بدء توليد صفوف اللهجات")
    rows = generate()
    ncand, ndone = mix_english(rows, random.Random(7))
    print("mix candidates", ncand, "applied", ndone)
    # التحقق الذاتي
    bad = []
    seenq = set()
    for r in rows:
        q, a = r["messages"][0]["content"], r["messages"][1]["content"]
        if NON_SAUDI_RE.search(q) or NON_SAUDI_RE.search(a): bad.append(("non-saudi", q[:60]))
        if DIALECT_ANS_RE.search(a): bad.append(("dialect-in-answer", DIALECT_ANS_RE.search(a).group(0), a[:60]))
        if wc(a) > 60: bad.append(("long", wc(a), a[:50]))
        if "{" in q or "}" in q: bad.append(("token", q[:60]))
        if norm(q) in seenq: bad.append(("dupq", q[:60]))
        seenq.add(norm(q))
    print("rows", len(rows), "bad", len(bad))
    for b in bad[:40]: print(b)
    print(collections.Counter(r["meta"]["region"] for r in rows))
    print(collections.Counter(r["meta"]["type"] for r in rows))
    lat = sum(1 for r in rows if re.search("[A-Za-z]", r["messages"][0]["content"]))
    print("latin", lat, lat / len(rows))
    w = BatchWriter(os.path.join(ROOT, "build", "out", "dialect_train.jsonl"), "dialect_train")
    for r in rows: w.add(r)
    w.close()
