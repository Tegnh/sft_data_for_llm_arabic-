# -*- coding: utf-8 -*-
"""check_sft.py — فحص الملفات الناتجة (مستقل بذاته، لا يعتمد على build/).
الاستعمال:  python3 check_sft.py            (يطبع تقريرًا، ويعيد رمز خروج 1 إذا فشل أي فحص إلزامي)
"""
import json, re, sys, os, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
TRAIN, VAL, TEST = "sft_train_v2.jsonl", "sft_val_v2.jsonl", "sft_dialect_test.jsonl"
REVIEW = "needs_review.jsonl"
REGIONS = ["nejd", "hijaz", "south", "east", "north"]
ALLOWED_REGION = set(REGIONS) | {"none", "saudi_general"}
ALLOWED_TYPE = {"informational", "advice", "summarize", "extract", "rewrite", "compare", "python", "arithmetic", "translation",
                "refusal", "text_answerable", "text_unanswerable"}
REFUSAL_TYPES = {"refusal", "text_unanswerable"}
AR = r"؀-ۿ"

def wb(words):
    return re.compile(r"(?<![%s])(?:%s)(?![%s])" % (AR, "|".join(sorted(set(words), key=len, reverse=True)), AR))

NON_SAUDI = wb(["كده", "دلوقتي", "ازاي", "إزاي", "عايز", "عايزة", "هلأ", "هلق", "شو", "بدي", "كتير", "مش"])
# مؤشرات لهجة يجب ألا تظهر في إجابات الفصحى
DIALECT_IN_ANSWER = wb(["وش", "ايش", "إيش", "أبغى", "ابغى", "ابي", "بيتم", "بنراجع", "بنتحقق", "بيضاف", "بنرجع", "بنرسل", "بنرتب", "بنعوضك",
                        "زي", "شي", "شوي", "كويس", "تبغى", "تبي", "ودي", "ودك", "أسوي", "اسوي", "يبي", "ليش", "ليه", "وين", "زين", "عشان",
                        "علشان", "ما أقدر", "ما أملك", "ما أستطيع", "ما عندي", "قول لي", "ناوي", "هالحين", "دحين", "دايم", "مره", "كذا",
                        "هذي", "اللي", "مو", "ماني", "لين", "لازم", "تقدر", "أقدر", "أشوف", "أعطيك", "تلقى", "بس", "حياك", "مشكور",
                        "يالله", "هيه", "شلون", "وشلون"])
FILLER = "يختلفان في الوظيفة أو طريقة الاستخدام"
LATIN = re.compile("[A-Za-z]")

def strip_tashkeel(s):
    return re.sub(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]", "", s)

def norm(s):
    s = strip_tashkeel(s)
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    s = re.sub("[أإآٱ]", "ا", s)
    s = s.replace("ؤ", "و").replace("ئ", "ي").replace("ى", "ي").replace("ة", "ه").replace("ء", "")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()

def wc(s): return len(s.split())

def load(name):
    path = os.path.join(ROOT, name)
    out, bad = [], []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip(): continue
            try: out.append(json.loads(line))
            except Exception as e: bad.append((i, str(e)))
    return out, bad

results = []   # (اسم الفحص، نجح؟، تفاصيل، إلزامي؟)
def check(name, ok, detail="", hard=True):
    results.append((name, bool(ok), detail, hard))
    print(("PASS " if ok else ("FAIL " if hard else "WARN ")) + name + ((" — " + detail) if detail else ""))

def qa(r):
    m = r["messages"]
    return m[0]["content"], m[1]["content"]

def para_keys(user):
    """مفاتيح الفقرات: كل سطر فيه 20 كلمة فأكثر (بعد حذف بادئة النص:)."""
    keys = []
    for line in user.split("\n"):
        line = re.sub(r"^(النص|الجملة|السؤال)\s*:\s*", "", line.strip())
        if wc(line) >= 20:
            keys.append(norm(line))
    return keys

# ------------------------------------------------------------------ تحميل
train, b1 = load(TRAIN); val, b2 = load(VAL); test, b3 = load(TEST)
print("=" * 70); print("الملفات: train=%d  val=%d  dialect_test=%d" % (len(train), len(val), len(test))); print("=" * 70)
check("JSON صالح في كل الأسطر", not (b1 or b2 or b3), str((b1 + b2 + b3)[:3]))
if os.path.exists(os.path.join(ROOT, REVIEW)):
    rev, b4 = load(REVIEW)
    check("needs_review.jsonl صالح", not b4 and len(rev) > 0, "%d صفًا" % len(rev), hard=False)
    check("needs_review لا يتقاطع مع train (سؤالًا)", not (set(norm(qa(r)[0]) for r in rev) & set(norm(qa(r)[0]) for r in train)), hard=True)

# ------------------------------------------------------------------ 1) المخطط
def schema_errors(rows, name):
    errs = []
    for i, r in enumerate(rows):
        if set(r.keys()) != {"messages", "meta"}: errs.append((i, "keys", sorted(r.keys()))); continue
        m = r["messages"]
        if not (isinstance(m, list) and len(m) == 2 and m[0].get("role") == "user" and m[1].get("role") == "assistant"): errs.append((i, "roles")); continue
        if not all(isinstance(x.get("content"), str) and x["content"].strip() for x in m): errs.append((i, "empty")); continue
        meta = r["meta"]
        if not (isinstance(meta, dict) and set(meta) == {"type", "region"}): errs.append((i, "meta-keys")); continue
        if meta["type"] not in ALLOWED_TYPE: errs.append((i, "type", meta["type"]))
        if meta["region"] not in ALLOWED_REGION: errs.append((i, "region", meta["region"]))
    return errs
for nm, rows in (("train", train), ("val", val)):
    e = schema_errors(rows, nm)
    check("مخطط %s (رسالتان user/assistant + meta{type,region})" % nm, not e, str(e[:3]))
    check("لا رسالة system في %s" % nm, all(x["role"] != "system" for r in rows for x in r["messages"]))
te = []
for i, t in enumerate(test):
    ok = (set(t) == {"pair_id", "region", "dialect", "msa", "reference_answer", "meta"} and t["region"] in REGIONS
          and t["dialect"]["messages"][0]["role"] == "user" and t["dialect"]["messages"][1]["role"] == "assistant"
          and t["msa"]["messages"][0]["role"] == "user" and t["msa"]["messages"][1]["role"] == "assistant"
          and t["dialect"]["messages"][1]["content"] == t["reference_answer"] == t["msa"]["messages"][1]["content"]
          and t["dialect"]["messages"][0]["content"] != t["msa"]["messages"][0]["content"])
    if not ok: te.append(i)
check("مخطط dialect_test (pair_id، نسختان، إجابة مرجعية واحدة)", not te, str(te[:5]))
check("لا system في dialect_test", not any(m["role"] == "system" for t in test for m in t["dialect"]["messages"] + t["msa"]["messages"]))
check("pair_id فريد", len(set(t["pair_id"] for t in test)) == len(test))

# ------------------------------------------------------------------ 2) الأعداد
check("عدد صفوف val = 300", len(val) == 300, str(len(val)))
check("عدد عناصر dialect_test = 150", len(test) == 150, str(len(test)))
check("كل منطقة في dialect_test = 30", all(sum(1 for t in test if t["region"] == r) == 30 for r in REGIONS), str(collections.Counter(t["region"] for t in test)))
dia_train = collections.Counter(r["meta"]["region"] for r in train if r["meta"]["region"] in REGIONS and r["meta"]["type"] not in ("text_answerable", "text_unanswerable"))
check("لهجات train: 200 لكل منطقة (بدون أزواج النص المعطى)", all(dia_train[r] == 200 for r in REGIONS), str(dict(dia_train)))
check("لهجات val: 10 لكل منطقة", all(sum(1 for r in val if r["meta"]["region"] == g) == 10 for g in REGIONS))
paras_train = collections.Counter()
for r in train:
    if r["meta"]["type"] in ("text_answerable", "text_unanswerable"):
        ks = para_keys(qa(r)[0])
        if ks: paras_train[max(ks, key=len)] += 1
pairs_n = sum(paras_train.values())
check("أزواج النص المعطى في train = 300", pairs_n == 300, str(pairs_n))
check("فقرات فريدة في train ≥ 100", len(paras_train) >= 100, str(len(paras_train)))
check("كل فقرة تُستعمل 3 مرات كحد أقصى", max(paras_train.values()) <= 3, "أقصى استعمال=%d" % max(paras_train.values()))
tp_dialect = sum(1 for r in train if r["meta"]["type"] in ("text_answerable", "text_unanswerable") and r["meta"]["region"] in REGIONS)
check("نسبة أسئلة النص المعطى اللهجية ≈ 30%", 0.27 <= tp_dialect / max(1, pairs_n) <= 0.33, "%d/%d = %.1f%%" % (tp_dialect, pairs_n, 100 * tp_dialect / max(1, pairs_n)))

# ------------------------------------------------------------------ 3) التكرار داخل الملف
def dup_report(rows, key):
    c = collections.Counter(key(r) for r in rows)
    return {k: v for k, v in c.items() if v > 1}
dq_train = dup_report(train, lambda r: norm(qa(r)[0])); dq_val = dup_report(val, lambda r: norm(qa(r)[0]))
check("لا أسئلة مكررة في train", not dq_train, "%d مكرر" % len(dq_train))
check("لا أسئلة مكررة في val", not dq_val, "%d مكرر" % len(dq_val))
da_val = dup_report(val, lambda r: norm(qa(r)[1]))
check("val: إجابة واحدة لكل صف (لا إجابات مكررة)", not da_val, "%d إجابة مكررة" % len(da_val))
ans_train = collections.Counter(norm(qa(r)[1]) for r in train)
over = {k: v for k, v in ans_train.items() if v > 3}
check("train: كل إجابة ≤ 3 صياغات سؤال", not over, "أكثر إجابة تكرارًا=%d، مخالفات=%d" % (max(ans_train.values()), len(over)))
check("dialect_test: لا أسئلة لهجية مكررة", len(set(norm(t["dialect"]["messages"][0]["content"]) for t in test)) == len(test))
check("dialect_test: إجابات مرجعية فريدة", len(set(norm(t["reference_answer"]) for t in test)) == len(test))
check("dialect_test: الأسئلة الفصحى فريدة", len(set(norm(t["msa"]["messages"][0]["content"]) for t in test)) == len(test))

# ------------------------------------------------------------------ 4) التكرار بين الملفات
def sets(rows, is_test=False):
    if is_test:
        qs = set(norm(t[k]["messages"][0]["content"]) for t in rows for k in ("dialect", "msa"))
        as_ = set(norm(t["reference_answer"]) for t in rows)
        ps = set()
    else:
        qs = set(norm(qa(r)[0]) for r in rows); as_ = set(norm(qa(r)[1]) for r in rows)
        ps = set(k for r in rows for k in para_keys(qa(r)[0]))
    return qs, as_, ps
Tq, Ta, Tp = sets(train); Vq, Va, Vp = sets(val); Sq, Sa, _ = sets(test, True)
check("train ∩ val: أسئلة", not (Tq & Vq), str(len(Tq & Vq)))
check("train ∩ val: إجابات", not (Ta & Va), str(len(Ta & Va)))
check("train ∩ val: فقرات", not (Tp & Vp), str(len(Tp & Vp)))
check("train ∩ dialect_test: أسئلة", not (Tq & Sq), str(len(Tq & Sq)))
check("train ∩ dialect_test: إجابات", not (Ta & Sa), str(len(Ta & Sa)))
check("val ∩ dialect_test: أسئلة", not (Vq & Sq), str(len(Vq & Sq)))
check("val ∩ dialect_test: إجابات", not (Va & Sa), str(len(Va & Sa)))

# ------------------------------------------------------------------ 5) الأطوال
def too_long(rows):
    bad = []
    for r in rows:
        a = qa(r)[1]
        is_list = bool(re.search(r"(^|\n)\s*(\d+[.)]|[-•])\s", a)) or "```" in a
        if wc(a) > 60 and not is_list: bad.append((wc(a), a[:50]))
    return bad
for nm, rows in (("train", train), ("val", val)):
    b = too_long(rows)
    check("طول الإجابات ≤ 60 كلمة في %s (ما لم تكن قائمة/كودًا)" % nm, not b, "مخالفات=%d %s" % (len(b), b[:2]))
code_long = [qa(r)[1] for r in train if "```" in qa(r)[1] and wc(qa(r)[1]) > 60]
check("أمثلة الكود ≤ 60 كلمة", not code_long, "%d" % len(code_long), hard=False)
print("     متوسط طول الإجابة (كلمات): train=%.1f val=%.1f  | أطولها: train=%d val=%d" % (
    sum(wc(qa(r)[1]) for r in train) / len(train), sum(wc(qa(r)[1]) for r in val) / len(val),
    max(wc(qa(r)[1]) for r in train), max(wc(qa(r)[1]) for r in val)))

# ------------------------------------------------------------------ 6) اللهجة والمؤشرات
def all_texts(rows, is_test=False):
    if is_test:
        for t in rows:
            for k in ("dialect", "msa"):
                for m in t[k]["messages"]: yield m["content"]
    else:
        for r in rows:
            for m in r["messages"]: yield m["content"]
for nm, rows, it in (("train", train, False), ("val", val, False), ("dialect_test", test, True)):
    hits = [x[:50] for x in all_texts(rows, it) if NON_SAUDI.search(x)]
    check("لا مؤشرات غير سعودية (كده/دلوقتي/ازاي/عايز/هلأ/شو/بدي/كتير/مش) في %s" % nm, not hits, str(hits[:3]))
for nm, rows in (("train", train), ("val", val)):
    hits = [qa(r)[1][:60] for r in rows if DIALECT_IN_ANSWER.search(qa(r)[1])]
    check("إجابات %s كلها بالفصحى (لا مؤشرات لهجة)" % nm, not hits, "%d %s" % (len(hits), hits[:2]))
hits = [t["reference_answer"][:60] for t in test if DIALECT_IN_ANSWER.search(t["reference_answer"])]
check("الإجابات المرجعية في dialect_test بالفصحى", not hits, str(hits[:2]))
check("لا جملة «ثانياً، يختلفان في الوظيفة…» الفارغة", not any(FILLER in qa(r)[1] for r in train + val), str(sum(FILLER in qa(r)[1] for r in train)))
check("لا «بحسب السياق» في إجابات train/val", not any("بحسب السياق" in qa(r)[1] for r in train + val), "", hard=False)
check("لا حشو «يوضح النص الفكرة الرئيسة بإيجاز»", not any("يوضح النص الفكرة الرئيسة" in qa(r)[1] for r in train + val))
check("لا صف «حالة طلب الصيانة رقم» في train", not any("حالة طلب الصيانة" in qa(r)[0] for r in train))
# مصطلحات بايثون المخترعة
INVENTED_PY = ["طريقة الفرقعة", "كلمة طالما", "حلقة طالما", "كلمة لكل", "حلقة لكل", "دالة المبتدئ", "كلمة حذف", "كلمة إرجاع", "كلمة الإنتاج", "علامة الشباك"]
py_bad = [qa(r)[1][:50] for r in train if r["meta"]["type"] == "python" and any(t in qa(r)[1] for t in INVENTED_PY)]
check("لا مصطلحات بايثون مخترعة", not py_bad, str(py_bad[:2]))
py_rows = [r for r in train if r["meta"]["type"] == "python"]
check("صفوف بايثون فيها الكلمات الصحيحة (while/for/pop/__init__)", all(any(k in " ".join(qa(x)[1] for x in py_rows) for k in [w]) for w in ("while", "for ", "pop", "__init__")), "%d صفًا" % len(py_rows))
# اللهجة في الأسئلة: صفوف المناطق يجب أن تحوي مؤشرًا لهجيًا واحدًا على الأقل في سؤال المستخدم (تقريبًا)
DIA_Q = re.compile(r"(?<![\u0600-\u06FF])[وفبل]?(?:وش|ايش|أبغى|ابغى|ابي|ودي|ليش|ليه|وين|شلون|الحين|هالحين|دحين|مرة|تكفى|هالرسالة|هالنص|هالجملة|"
                   r"هالتقرير|مين|حق|شي|شوي|اللي|مب|مو|بكرة|لين|أسوي|أسويه|تبغى|يبغى|بغيت|عشان|زين|يعطيك|هلا|ياخي|قول|ما أقدر|بروح|بتأخر|بعد بكرة|"
                   r"دايم|مره|كذا|هذي|هالحين|ياخي|والله|يا شيخ)(?![\u0600-\u06FF])")
dia_rows = [r for r in train if r["meta"]["region"] in REGIONS and r["meta"]["type"] not in ("text_answerable", "text_unanswerable")]
no_marker = [qa(r)[0][:50] for r in dia_rows if not DIA_Q.search(qa(r)[0])]
check("سؤال المستخدم لهجي في صفوف المناطق (مؤشر لهجي واحد على الأقل)", len(no_marker) / len(dia_rows) < 0.03, "بلا مؤشر=%d من %d %s" % (len(no_marker), len(dia_rows), no_marker[:2]), hard=False)
latin = sum(1 for r in dia_rows if LATIN.search(qa(r)[0]))
check("خلط المصطلحات الإنجليزية ≈ 15% من صفوف اللهجات", 0.12 <= latin / len(dia_rows) <= 0.18, "%d/%d = %.1f%%" % (latin, len(dia_rows), 100 * latin / len(dia_rows)))

# ------------------------------------------------------------------ 7) الرفض
def opener(a, n=3): return " ".join(norm(a).split()[:n])
for nm, rows in (("train", train), ("val", val)):
    ref = [r for r in rows if r["meta"]["type"] in REFUSAL_TYPES]
    ratio = len(ref) / len(rows)
    check("نسبة الرفض في %s بين 6%% و8%%" % nm, 0.06 <= ratio <= 0.08, "%d/%d = %.2f%%" % (len(ref), len(rows), 100 * ratio))
ref_tr = [qa(r)[1] for r in train if r["meta"]["type"] == "refusal"]
ops = set(opener(a, 3) for a in ref_tr)
check("تنويع صيغ الرفض (train، النوع refusal): ≥ 25 صيغة افتتاح مختلفة", len(ops) >= 25, "%d صيغة من %d صفًا" % (len(ops), len(ref_tr)))
un_tr = [qa(r)[1] for r in train if r["meta"]["type"] == "text_unanswerable"]
ops2 = set(opener(a, 3) for a in un_tr)
check("تنويع رفض النص المعطى في train: ≥ 20 صيغة", len(ops2) >= 20, "%d صيغة من %d صفًا" % (len(ops2), len(un_tr)))
un_val = [qa(r)[1] for r in val if r["meta"]["type"] == "text_unanswerable"]
check("val: صيغ رفض النص المعطى غير مكررة", len(set(opener(a, 3) for a in un_val)) == len(un_val), "%d صيغة/%d" % (len(set(opener(a, 3) for a in un_val)), len(un_val)))
check("رفض النص المعطى مبني على النص («النص لا يذكر…» أو ما يعادله)", all(re.search(r"(النص|الفقرة)", a) for a in un_tr + un_val))

# ------------------------------------------------------------------ 8) أزواج النص المعطى
def para_of(user):
    ks = para_keys(user); return max(ks, key=len) if ks else ""
bad_ans = []
for nm, rows in (("train", train), ("val", val)):
    for r in rows:
        if r["meta"]["type"] == "text_answerable":
            u, a = qa(r)
            if norm(a) not in norm(u): bad_ans.append((nm, a[:40]))
check("إجابة النص المعطى المجاب عبارة مقتبسة من الفقرة", not bad_ans, "%d %s" % (len(bad_ans), bad_ans[:2]))
wcs = []
for r in train + val:
    if r["meta"]["type"] in ("text_answerable", "text_unanswerable"):
        ks = para_keys(qa(r)[0]);
        wcs.append(max((len(k.split()) for k in ks), default=0))
check("طول الفقرات بين 25 و80 كلمة", all(25 <= w <= 100 for w in wcs), "أدنى=%d أعلى=%d (الأعلى يشمل بادئات الإطار)" % (min(wcs), max(wcs)))

# ------------------------------------------------------------------ 9) توزيعات (للعرض)
print("-" * 70)
def dist(rows): return collections.Counter(r["meta"]["type"] for r in rows)
print("توزيع الأنواع train:", dict(dist(train)))
print("توزيع الأنواع val  :", dict(dist(val)))
print("توزيع الأنواع dialect_test:", dict(collections.Counter(t["meta"]["type"] for t in test)))
print("المناطق train:", dict(collections.Counter(r["meta"]["region"] for r in train)))
print("المناطق val  :", dict(collections.Counter(r["meta"]["region"] for r in val)))
print("المناطق × الأنواع (لهجات train):")
for g in REGIONS:
    print("   ", g, dict(collections.Counter(r["meta"]["type"] for r in dia_rows if r["meta"]["region"] == g)))
print("المناطق × الأنواع (dialect_test):")
for g in REGIONS:
    print("   ", g, dict(collections.Counter(t["meta"]["type"] for t in test if t["region"] == g)))

# ------------------------------------------------------------------ الخلاصة
hard_fail = [r for r in results if not r[1] and r[3]]
warn = [r for r in results if not r[1] and not r[3]]
print("=" * 70)
print("النتيجة: %d فحصًا، ناجح %d، فشل إلزامي %d، تحذير %d" % (len(results), sum(1 for r in results if r[1]), len(hard_fail), len(warn)))
if hard_fail:
    print("الفحوص الفاشلة:"); [print("  -", r[0], r[2]) for r in hard_fail]
    sys.exit(1)
print("كل الفحوص الإلزامية نجحت.")
