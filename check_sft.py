# -*- coding: utf-8 -*-
"""check_sft.py (v3) — فحص ملفات SFT v3.
الاستعمال:  python3 check_sft.py            (يخرج برمز 1 إذا فشل أي فحص إلزامي)
الملفات: build/v3/sft_train_v3.jsonl و build/v3/sft_val_v3.jsonl (+ sft_dialect_test.jsonl للتقاطع).
النسخة السابقة (v2) محفوظة في build/v3/check_sft_v2_legacy.py.
"""
import json, re, sys, os, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "build", "v3", "tools"))
import v3lib as L

TRAIN = os.path.join(ROOT, "build", "v3", "sft_train_v3.jsonl")
VAL = os.path.join(ROOT, "build", "v3", "sft_val_v3.jsonl")
TEST = os.path.join(ROOT, "sft_dialect_test.jsonl")
SHA_FILE = os.path.join(ROOT, "build", "v3", "original_sha256.txt")
REGIONS = L.REGIONS
norm, wc = L.norm, L.wc

results = []   # (رقم، اسم، ناجح؟، تفاصيل، إلزامي؟)
def check(num, name, ok, detail="", hard=True):
    results.append((num, name, bool(ok), detail, hard))
    tag = "PASS" if ok else ("FAIL" if hard else "WARN")
    print(f"{tag} [{num}] {name}" + (f" — {detail}" if detail else ""))

def load(path):
    rows, bad = [], []
    for i, line in enumerate(open(path, encoding="utf-8"), 1):
        if not line.strip(): continue
        try: rows.append(json.loads(line))
        except Exception as e: bad.append((i, str(e)))
    return rows, bad

train, b1 = load(TRAIN); val, b2 = load(VAL); test, b3 = load(TEST)
lex = L.parse_lexicon(); lex_u = L.usable(lex)
print("=" * 78)
print(f"الملفات: train={len(train)} val={len(val)} dialect_test={len(test)}")
print("=" * 78)

def q1(r): return r["messages"][0]["content"]
def a_last(r): return r["messages"][-1]["content"]
def users(r): return "\n".join(m["content"] for m in r["messages"] if m["role"] == "user")

# ---------------------------------------------------------------- 1) الصيغة
def fmt_errors(rows, split):
    errs = []
    for i, r in enumerate(rows):
        e = L.row_errors(r, lex_u, split=split)
        e = [x for x in e if x.startswith(("مفاتيح", "عدد الرسائل", "الأدوار", "محتوى فارغ", "type غير", "region غير", "split", "confidence", "multi_turn"))]
        if e: errs.append((i, e[0]))
    return errs
e1, e2 = fmt_errors(train, "train"), fmt_errors(val, "val")
sysmsg = sum(1 for r in train + val for m in r["messages"] if m["role"] == "system")
check(1, "الصيغة صحيحة، أدوار متناوبة، لا system، مفاتيح meta المطلوبة", not (b1 or b2 or b3 or e1 or e2 or sysmsg), f"أخطاء train={len(e1)} val={len(e2)} json={len(b1+b2+b3)} system={sysmsg} {(e1+e2)[:2]}")
# ---------------------------------------------------------------- 2) الأعداد
check(2, "train = 4000 بالضبط وval = 500 بالضبط", len(train) == 4000 and len(val) == 500, f"train={len(train)} val={len(val)}")
# ---------------------------------------------------------------- 3) التقاطع
def para_keys(r):
    out = []
    for line in users(r).split("\n"):
        line = re.sub(r"^(النص|الجملة|السؤال)\s*:\s*", "", line.strip())
        if wc(line) >= 20: out.append(norm(line))
    return out
def sets_of(rows, is_test=False):
    if is_test:
        qs = {norm(t[k]["messages"][0]["content"]) for t in rows for k in ("dialect", "msa")}
        as_ = {norm(t["reference_answer"]) for t in rows}
        return qs, as_, set()
    return {norm(q1(r)) for r in rows}, {norm(a_last(r)) for r in rows}, {k for r in rows for k in para_keys(r)}
Tq, Ta, Tp = sets_of(train); Vq, Va, Vp = sets_of(val); Sq, Sa, Sp = sets_of(test, True)
def shingle_set(rows):
    s = set()
    for r in rows:
        for line in users(r).split("\n"):
            if wc(line) >= 20: s |= L.shingles(line, 10)
    return s
Tsh, Vsh = shingle_set(train), shingle_set(val)
Ssh = set()
for t in test:
    for k in ("dialect", "msa"):
        for line in t[k]["messages"][0]["content"].split("\n"):
            if wc(line) >= 20: Ssh |= L.shingles(line, 10)
ov = {"سؤال train∩val": len(Tq & Vq), "سؤال train∩test": len(Tq & Sq), "سؤال val∩test": len(Vq & Sq),
      "إجابة train∩val": len(Ta & Va), "إجابة train∩test": len(Ta & Sa), "إجابة val∩test": len(Va & Sa),
      "فقرة train∩val": len(Tp & Vp) + len(Tsh & Vsh), "فقرة train∩test": len(Tsh & Ssh), "فقرة val∩test": len(Vsh & Ssh)}
check(3, "لا تداخل (بعد التطبيع) في السؤال أو الإجابة أو الفقرة بين train وval وdialect_test", not any(ov.values()), str({k: v for k, v in ov.items() if v}) or "0")
# ---------------------------------------------------------------- 4) التكرار
cnt = collections.Counter(norm(a_last(r)) for r in train)
over = {k: v for k, v in cnt.items() if v > 3}
reg_of = collections.defaultdict(set)
for r in train:
    if r["meta"]["region"] in REGIONS: reg_of[norm(a_last(r))].add(r["meta"]["region"])
multi_reg = {k: v for k, v in reg_of.items() if len(v) > 2}
vcnt = collections.Counter(norm(a_last(r)) for r in val)
vdup = {k: v for k, v in vcnt.items() if v > 1}
check(4, "إجابة ≤ 3 مرات في train، وفي ≤ منطقتين، وإجابات val فريدة", not (over or multi_reg or vdup),
      f"مكررة>3={len(over)} في>2 مناطق={len(multi_reg)} تكرار val={len(vdup)}")
# ---------------------------------------------------------------- 5) المؤشرات الإقليمية
def marker_errors(rows):
    bad = []
    for i, r in enumerate(rows):
        reg = r["meta"]["region"]
        if reg not in REGIONS and reg != "saudi_general": continue
        e = [x for x in L.row_errors(r, lex_u) if ("المؤشر" in x or "dialect_markers" in x or "لا مؤشر خاص" in x or "غير سعودي" in x or "مفردات منطقة" in x or "مفردات إقليمية" in x)]
        if e: bad.append((i, e[0]))
    return bad
m1, m2 = marker_errors(train), marker_errors(val)
non_saudi = [i for i, r in enumerate(train + val) if L.NON_SAUDI.search(users(r))]
nreg_tr = sum(1 for r in train if r["meta"]["region"] in REGIONS or r["meta"]["region"] == "saudi_general")
check(5, "كل صف إقليمي: markers غير فارغة، حرفية في سؤال المستخدم، من المعجم، ولا مؤشر غير سعودي", not (m1 or m2 or non_saudi),
      f"صفوف إقليمية/عامة train={nreg_tr} | أخطاء train={len(m1)} val={len(m2)} غير سعودي={len(non_saudi)} {(m1+m2)[:2]}")
# ---------------------------------------------------------------- 6) فصحى الإجابات
dia_bad = []
for name, rows in (("train", train), ("val", val)):
    for i, r in enumerate(rows):
        if r["meta"]["type"] in ("rewrite", "summarize"): continue
        for m in r["messages"]:
            if m["role"] == "assistant" and L.DIALECT_IN_ANSWER.search(m["content"]): dia_bad.append((name, i, L.DIALECT_IN_ANSWER.search(m["content"]).group(0)))
check(6, "إجابات المساعد بالفصحى (لا مفردات لهجة إلا اقتباسًا في rewrite/summarize)", not dia_bad, f"{len(dia_bad)} {dia_bad[:3]}")
# ---------------------------------------------------------------- 7) نسبة الرفض
def ratio(rows): return sum(1 for r in rows if r["meta"]["type"] in L.REFUSAL_TYPES) / max(1, len(rows))
rt, rv = ratio(train), ratio(val)
check(7, "نسبة (refusal + text_unanswerable): train 6–8%، val 5–8%", 0.06 <= rt <= 0.08 and 0.05 <= rv <= 0.08, f"train={100*rt:.2f}% val={100*rv:.2f}%")
# ---------------------------------------------------------------- 8) اختراع سياسة
inv = []
for name, rows in (("train", train), ("val", val)):
    for i, r in enumerate(rows):
        u = norm(users(r))
        for m in r["messages"]:
            if m["role"] != "assistant": continue
            for p in L.POLICY_RE:
                mm = p.search(m["content"])
                if mm and norm(mm.group(0)) not in u and not (re.search(r"\d", mm.group(0)) and re.search(r"\d+", mm.group(0)).group(0) in users(r)):
                    inv.append((name, i, mm.group(0)))
check(8, "لا نمط اختراع سياسة أو حالة (regex)", not inv, f"{len(inv)} {inv[:3]}")
# ---------------------------------------------------------------- 9) الطول
lng = []
for name, rows in (("train", train), ("val", val)):
    for i, r in enumerate(rows):
        for m in r["messages"]:
            if m["role"] == "assistant":
                a = m["content"]; lim = 120 if L.is_list(a) else 60
                if wc(a) > lim: lng.append((name, i, wc(a)))
check(9, "طول كل إجابة ≤ 60 كلمة (والقوائم ≤ 120)", not lng, f"{len(lng)} {lng[:3]}")
# ---------------------------------------------------------------- 10) الحسابيات
ar_bad, ar_n, ar_eq = [], 0, 0
for name, rows in (("train", train), ("val", val)):
    for i, r in enumerate(rows):
        if r["meta"]["type"] == "arithmetic":
            ar_n += 1; p, n = L.arithmetic_problems(q1(r), a_last(r)); ar_eq += n
            if p: ar_bad.append((name, i, p[:1]))
check(10, "الحسابيات تُعاد بالكود", not ar_bad, f"صفوف={ar_n} معادلات مفحوصة={ar_eq} أخطاء={len(ar_bad)} {ar_bad[:2]}")
# ---------------------------------------------------------------- 11) توزيع val
vt = collections.Counter(r["meta"]["type"] for r in val)
vreg = collections.Counter(r["meta"]["region"] for r in val)
text_given = sum(1 for r in val if para_keys(r))
unans = vt["text_unanswerable"]; refs = vt["refusal"] + vt["text_unanswerable"]
top = max(vt.values()) / len(val)
ok11 = (sum(vreg[g] for g in REGIONS) >= 50 and all(vreg[g] >= 10 for g in REGIONS) and text_given >= 60 and unans >= 20 and refs >= 30 and vt["multi_turn"] >= 30 and top <= 0.30)
check(11, "val: إقليمي≥50 (≥10/منطقة)، نص معطى≥60 (غير مجاب≥20)، refusal(+غير مجاب)≥30، multi_turn≥30، لا نوع>30%", ok11,
      f"إقليمي={sum(vreg[g] for g in REGIONS)} {dict((g, vreg[g]) for g in REGIONS)} | نص معطى={text_given} غير مجاب={unans} | refusal={vt['refusal']} refusal+غير مجاب={refs} | multi_turn={vt['multi_turn']} | أكبر نوع={100*top:.1f}%")
# ---------------------------------------------------------------- 12) sha256
sha_ok, sha_msg = True, []
for line in open(SHA_FILE, encoding="utf-8"):
    h, name = line.split()
    cur = L.sha256(os.path.join(ROOT, name))
    if cur != h: sha_ok = False; sha_msg.append(name)
check(12, "sha256 للملفات الأصلية الأربعة لم يتغير", sha_ok, ",".join(sha_msg) or "مطابق")

# ---------------------------------------------------------------- فحوص إضافية (معلوماتية/تحذيرية)
print("-" * 78)
new_g = [r for r in train if r["meta"]["source"] == "v3-practical-grounded"]
pu = collections.Counter(max(para_keys(r), key=len) for r in new_g if para_keys(r))
check("x1", "الفقرات الجديدة في train ≥ 100 وكل فقرة ≤ 3 استعمالات", len(pu) >= 100 and (max(pu.values()) <= 3 if pu else True), f"فقرات={len(pu)} أقصى استعمال={max(pu.values()) if pu else 0}", hard=False)
vg = [r for r in val if r["meta"]["source"] == "v3-practical-grounded"]
vpu = collections.Counter(max(para_keys(r), key=len) for r in vg if para_keys(r))
check("x2", "فقرات val الجديدة ≤ 3 استعمالات", (max(vpu.values()) <= 3 if vpu else True), f"فقرات={len(vpu)}", hard=False)
old_sh = set()
for r in train + val:
    if r["meta"]["source"] == "v2":
        for line in users(r).split("\n"):
            if wc(line) >= 20: old_sh |= L.shingles(line, 10)
new_sh = set()
for r in new_g + vg:
    for line in users(r).split("\n"):
        if wc(line) >= 20: new_sh |= L.shingles(line, 10)
check("x3", "لا فقرة مشتركة بين فقرات practical-grounded وفقرات v2/dialect_test", not (new_sh & (old_sh | Ssh)), str(len(new_sh & (old_sh | Ssh))), hard=False)
pm = [r for r in train + val if r["meta"]["source"] == "v3-practical-messages"]
pmc = collections.Counter((r["meta"]["split"], r["meta"]["type"]) for r in pm)
check("x4", "practical-messages: 200 train/50 val، clarify 60، multi_turn 30/15", sum(1 for r in pm if r["meta"]["split"] == "train") == 200 and sum(1 for r in pm if r["meta"]["split"] == "val") == 50
      and pmc[("train", "clarify")] + pmc[("val", "clarify")] == 60 and pmc[("train", "multi_turn")] == 30 and pmc[("val", "multi_turn")] == 15, str(dict(pmc)), hard=False)
pg = [r for r in train + val if r["meta"]["source"] == "v3-practical-grounded"]
pgc = collections.Counter(r["meta"]["split"] for r in pg)
mt_g = collections.Counter((r["meta"]["split"]) for r in pg if r["meta"]["type"] == "multi_turn")
check("x5", "practical-grounded: 239 train/100 val، multi_turn 30/15", pgc["train"] == 239 and pgc["val"] == 100 and mt_g["train"] == 30 and mt_g["val"] == 15, f"{dict(pgc)} multi={dict(mt_g)}", hard=False)
dsrc = collections.Counter((r["meta"]["source"], r["meta"]["split"]) for r in train + val if r["meta"]["source"].startswith("v3-dialect"))
new_dia_ok = all(sum(v for (s, sp), v in dsrc.items() if s == f"v3-dialect-{g}" and sp == "train") >= 40 for g in REGIONS)
check("x6", "وكلاء اللهجات: عدد صفوفهم في train/val ≥ المطلوب", new_dia_ok, str(dict(dsrc)), hard=False)
lat = sum(1 for r in train + val if r["meta"]["source"].startswith("v3-dialect") and re.search("[A-Za-z]", users(r)))
nd = sum(1 for r in train + val if r["meta"]["source"].startswith("v3-dialect"))
check("x7", "خلط الإنجليزية التقني ≈ 20% في صفوف اللهجات الجديدة/المعاد كتابتها (تقريبي)", True, f"{lat}/{nd}", hard=False)
pol_r = collections.Counter(r["meta"]["region"] for r in train)
print("توزيع المناطق train:", dict(pol_r)); print("توزيع المناطق val  :", dict(vreg))
print("توزيع الأنواع train:", dict(collections.Counter(r["meta"]["type"] for r in train)))
print("توزيع الأنواع val  :", dict(vt))
print("المصادر train:", dict(collections.Counter(r["meta"]["source"] for r in train)))
print("المصادر val  :", dict(collections.Counter(r["meta"]["source"] for r in val)))

mand = [r for r in results if isinstance(r[0], int)]
failed = [f"[{r[0]}] {r[1]}" for r in mand if not r[2]]
print("=" * 78)
print(f"الفحوص الإلزامية: {sum(1 for r in mand if r[2])}/{len(mand)} ناجحة؛ التحذيرات: {sum(1 for r in results if not isinstance(r[0], int) and not r[2])}")
if failed:
    print("FAILED: " + " | ".join(failed)); sys.exit(1)
print("ALL_MANDATORY_CHECKS_PASSED")
