# -*- coding: utf-8 -*-
"""مكتبة مشتركة لأدوات v3: التطبيع، المعجم، فحص الصف، الحسابيات."""
import json, re, os, collections, hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(ROOT, "build", "v3")
REGIONS = ["nejd", "hijaz", "south", "east", "north"]
ALLOWED_REGION = set(REGIONS) | {"none", "saudi_general"}
ALLOWED_TYPE = {"informational", "advice", "rewrite", "summarize", "extract", "text_answerable", "text_unanswerable", "refusal",
                "arithmetic", "python", "translation", "compare", "clarify", "multi_turn"}
REFUSAL_TYPES = {"refusal", "text_unanswerable"}
META_KEYS = {"type", "region", "split", "dialect_markers", "confidence", "source"}
AR = "\u0621-\u063A\u0641-\u065F\u0670-\u06D3"

def wb(words):
    return re.compile(r"(?<![%s])(?:%s)(?![%s])" % (AR, "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True)), AR))

NON_SAUDI = wb(["كده", "دلوقتي", "ازاي", "إزاي", "عايز", "عايزة", "هلأ", "هلق", "شو", "بدي", "كتير", "مش"])
DIALECT_IN_ANSWER = wb(["وش", "ايش", "إيش", "أبغى", "ابغى", "ابي", "بيتم", "بنراجع", "بنتحقق", "بيضاف", "بنرجع", "بنرسل", "بنرتب", "بنعوضك",
                        "زي", "شي", "شوي", "كويس", "تبغى", "تبي", "ودي", "ودك", "أسوي", "اسوي", "يبي", "ليش", "ليه", "وين", "زين", "عشان",
                        "علشان", "ما أقدر", "ما أملك", "ما أستطيع", "ما عندي", "قول لي", "ناوي", "هالحين", "دحين", "دايم", "مره", "كذا",
                        "هذي", "اللي", "مو", "ماني", "لين", "لازم", "تقدر", "أقدر", "أشوف", "أعطيك", "تلقى", "بس", "حياك", "مشكور",
                        "يالله", "هيه", "شلون", "وشلون"])
# أنماط اختراع سياسة/خدمة/حالة (تُطبَّق على الإجابة، وتُتجاهل إن وردت العبارة نفسها في سؤال المستخدم)
POLICY_PATTERNS = [r"عندنا سياسة", r"لدينا سياسة", r"سياستنا", r"سياسة (?:الاسترجاع|الإرجاع|الاستبدال|مطابقة)", r"مطابقة (?:السعر|الأسعار)",
                   r"(?:يغطيه|تغطيه|يغطيها|تشمله|تشملها) (?:الضمان|سياسة الضمان)", r"(?:يشمله|تشمله|تشملها) الضمان", r"يغطي الضمان", r"يغطيها الضمان",
                   r"(?:يمكنك|تقدر|بإمكانك) (?:إرجاع|استرجاع|استبدال)", r"خلال \d+ (?:يوم|أيام) من (?:الشراء|الاستلام)",
                   r"حالة (?:طلبك|الطلب)\s*:", r"رقم الطلب\s*:\s*\d", r"طلبك (?:في الطريق|قيد|تم شحنه|سيصل)", r"سيصلك (?:طلبك )?(?:خلال|في يوم)",
                   r"موعدك (?:يوم|الساعة)", r"تم (?:حجز|تأكيد) موعدك", r"الفنيين لدينا", r"فروعنا", r"أقرب فرع لدينا", r"(?:نقدر|نستطيع|سنقوم|بنقدر) (?:نتحقق|نعوضك|نرجع)",
                   r"رسوم (?:الشحن|التوصيل) (?:مجانية|\d)", r"شحن مجاني", r"خصم \d+%"]
POLICY_RE = [re.compile(p) for p in POLICY_PATTERNS]
LATIN = re.compile("[A-Za-z]")

def strip_tashkeel(s):
    return re.sub("[ؐ-ًؚ-ٰٟۖ-ۭـ]", "", s)

def norm(s):
    s = strip_tashkeel(s)
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    s = re.sub("[أإآٱ]", "ا", s)
    s = s.replace("ؤ", "و").replace("ئ", "ي").replace("ى", "ي").replace("ة", "ه").replace("ء", "")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()

def wc(s): return len(s.split())

def load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip(): out.append(json.loads(line))
    return out

def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")

def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

def user_texts(row): return [m["content"] for m in row["messages"] if m["role"] == "user"]
def asst_texts(row): return [m["content"] for m in row["messages"] if m["role"] == "assistant"]
def first_q(row): return row["messages"][0]["content"]
def last_a(row): return row["messages"][-1]["content"]

def para_keys(user):
    keys = []
    for line in user.split("\n"):
        line = re.sub(r"^(النص|الجملة|السؤال)\s*:\s*", "", line.strip())
        if wc(line) >= 20: keys.append(norm(line))
    return keys

def shingles(text, n=10):
    w = norm(text).split()
    return {" ".join(w[i:i + n]) for i in range(0, max(0, len(w) - n + 1))}

# ------------------------------------------------------------------ المعجم
def parse_lexicon(path=None):
    """يعيد {region: [(word, example, conf)]} — الأقسام: nejd hijaz south east north saudi_general"""
    path = path or os.path.join(V3, "dialect_lexicon.md")
    lex, cur = {}, None
    if not os.path.exists(path): return lex
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^##\s+([a-z_]+)\b", line.strip())
        if m:
            cur = m.group(1); lex.setdefault(cur, []); continue
        if cur and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[2].lower() in ("high", "medium", "low"):
                lex[cur].append((cells[0], cells[1], cells[2].lower()))
    return lex

def usable(lex):
    """المفردات المسموحة (high/medium فقط): {region: {word: conf}}"""
    return {r: {w: c for w, _, c in v if c in ("high", "medium")} for r, v in lex.items()}

_pref = "[وفبل]?"
def word_re(word):
    return re.compile(r"(?<![%s])%s%s(?![%s])" % (AR, _pref, re.escape(word), AR))

_cache = {}
def find_markers(text, lex_usable):
    """يعيد {region: [words]} لكل المفردات المعجمية المسموحة الظاهرة في النص"""
    out = {}
    for reg, words in lex_usable.items():
        hits = []
        for w in words:
            k = w
            if k not in _cache: _cache[k] = word_re(w)
            if _cache[k].search(text) and w in text: hits.append(w)
        if hits: out[reg] = hits
    return out

def lexicon_problems(lex):
    probs = []
    for r in REGIONS:
        n = len([1 for w, _, c in lex.get(r, []) if c in ("high", "medium")])
        if not (25 <= len(lex.get(r, [])) <= 40): probs.append(f"{r}: عدد المفردات {len(lex.get(r, []))} خارج 25-40")
        if n < 20: probs.append(f"{r}: high/medium أقل من 20")
    if "saudi_general" not in lex or len(lex["saudi_general"]) < 15: probs.append("saudi_general ناقص")
    seen = {}
    for r, v in lex.items():
        for w, ex, c in v:
            if w in seen and seen[w] != r: probs.append(f"'{w}' مكررة في {seen[w]} و{r}")
            seen.setdefault(w, r)
            if w not in ex: probs.append(f"{r}: المثال لا يحوي المفردة '{w}'")
            if NON_SAUDI.search(w): probs.append(f"{r}: مفردة غير سعودية '{w}'")
    return probs

# ------------------------------------------------------------------ الحسابيات
_EXPR = re.compile(r"[\d(][\d.,()\s+\-×÷*/xX%]*[\d)%]")
def _val(e):
    e = e.strip()
    if re.fullmatch(r"[\d.,]+\s*%", e): e = e.rstrip("%")
    else: e = re.sub(r"([\d.]+)\s*%", r"(\1/100)", e)
    e = e.replace("×", "*").replace("÷", "/").replace("x", "*").replace("X", "*")
    e = re.sub(r"(?<=\d),(?=\d{3}\b)", "", e).replace(",", ".")
    if not re.fullmatch(r"[\d.()\s+\-*/]+", e): return None
    try: return float(eval(e, {"__builtins__": {}}, {}))
    except Exception: return None

def _pure(seg):
    """الجزء تعبير عددي صرف (يسمح بوحدة/كلمة بعد الرقم)؟ يعيد التعبير أو None"""
    seg = seg.strip()
    m = re.fullmatch(r"([\d(][\d.,()\s+\-×÷*/xX%]*[\d)%])(?:\s*[^\d\s+\-×÷*/()=≈][^\d=≈]*)?", seg)
    return m.group(1) if m else None

def arithmetic_problems(question, answer):
    """يتحقق من سلاسل a = b = c داخل كل جملة في الإجابة. يعيد (مشكلات، عدد المعادلات المفحوصة)"""
    a = answer.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,"))
    probs, n_eq = [], 0
    for sent in re.split(r"\.(?:\s|$)|[؛\n]|،\s", a):
        if "=" not in sent and "≈" not in sent: continue
        parts = re.split(r"([=≈])", sent)
        segs, ops = parts[0::2], parts[1::2]
        for j, op in enumerate(ops):
            l, r = _pure(segs[j]), _pure(segs[j + 1])
            if j == 0 and l is None:   # الجزء الأول قد يكون وسمًا لفظيًا: نأخذ تعبيرًا ذا عملية في آخره
                ms = [x for x in _EXPR.findall(segs[0]) if re.search(r"[+\-×÷*/]", x)]
                if ms and segs[0].rstrip().endswith(ms[-1].rstrip()): l = ms[-1].strip(); segs[0] = l
                else: continue
            if l is None or r is None: continue
            ul, ur = segs[j].strip()[len(l):].strip().split(" ")[0], segs[j + 1].strip()[len(r):].strip().split(" ")[0]
            if ul and ur and ul != ur: continue   # تحويل وحدات
            lv, rv = _val(l), _val(r)
            if lv is None or rv is None: continue
            n_eq += 1
            ok = abs(lv - rv) <= (0.006 + 1e-9 * abs(lv)) if op == "=" else abs(lv - rv) <= 0.06 * max(1, abs(lv))
            if not ok: probs.append(f"{l.strip()} {op} {r.strip()} ({lv:g} vs {rv:g})")
    return probs, n_eq

# ------------------------------------------------------------------ فحص الصف
def is_list(a):
    return bool(re.search(r"(^|\n)\s*(\d+[.)\-]|[-•*])\s", a)) or "```" in a

def is_cultural(w):
    """مفردة ثقافية/مكانية (تبدأ بأل أو عبارة من كلمتين) — مسموحة في نصوص region=none"""
    return w.startswith("ال") or " " in w

def row_errors(row, lex_u, split=None, agent=None, task=False):
    """أخطاء الصف الواحد بمعزل عن بقية الملف."""
    E = []
    if not isinstance(row, dict): return ["ليس كائنًا"]
    extra = set(row) - {"messages", "meta", "task_id"}
    if extra or "messages" not in row or "meta" not in row: E.append(f"مفاتيح غير صحيحة {sorted(row)}"); return E
    m, meta = row["messages"], row["meta"]
    if not isinstance(meta, dict) or set(meta) != META_KEYS: E.append(f"مفاتيح meta يجب أن تكون {sorted(META_KEYS)}"); return E
    if not isinstance(m, list) or len(m) < 2 or len(m) % 2: E.append("عدد الرسائل غير صحيح"); return E
    for i, x in enumerate(m):
        if x.get("role") != ("user" if i % 2 == 0 else "assistant"): E.append("الأدوار غير متناوبة أو system موجود"); return E
        if not isinstance(x.get("content"), str) or not x["content"].strip(): E.append("محتوى فارغ"); return E
    t, reg = meta["type"], meta["region"]
    if t not in ALLOWED_TYPE: E.append(f"type غير مسموح {t}")
    if reg not in ALLOWED_REGION: E.append(f"region غير مسموح {reg}")
    if meta["split"] not in ("train", "val"): E.append("split غير صحيح")
    elif split and meta["split"] != split: E.append(f"split يجب أن يكون {split}")
    if meta["confidence"] not in ("high", "medium"): E.append("confidence يجب high|medium")
    if agent and meta["source"] != f"v3-{agent}": E.append(f"source يجب أن يكون v3-{agent}")
    if (t == "multi_turn") != (len(m) == 4): E.append("multi_turn يجب أن يكون بالضبط دورين (4 رسائل) وغيره رسالتان")
    users = "\n".join(user_texts(row))
    if NON_SAUDI.search(users): E.append("مؤشر غير سعودي في سؤال المستخدم")
    # اللهجة والمؤشرات
    mk = meta["dialect_markers"]
    found = find_markers(users, lex_u)
    if reg in REGIONS:
        if not isinstance(mk, list) or not mk: E.append("dialect_markers فارغة في صف إقليمي")
        else:
            for w in mk:
                if w not in users: E.append(f"المؤشر '{w}' ليس حرفيًا في السؤال")
                if w not in lex_u.get(reg, {}) and w not in lex_u.get("saudi_general", {}): E.append(f"المؤشر '{w}' ليس في معجم {reg}/saudi_general")
            if not any(w in lex_u.get(reg, {}) for w in mk): E.append(f"لا مؤشر خاص بمنطقة {reg} (كلها عامة)")
        others = [(r2, [w for w in ws if not is_cultural(w)]) for r2, ws in found.items() if r2 in REGIONS and r2 != reg]
        others = [x for x in others if x[1]]
        if others: E.append(f"سؤال المستخدم يحوي مفردات منطقة أخرى {others}")
    elif reg == "saudi_general":
        if not isinstance(mk, list) or not mk: E.append("dialect_markers فارغة في saudi_general")
        else:
            for w in mk:
                if w not in users: E.append(f"المؤشر '{w}' ليس حرفيًا في السؤال")
                if w not in lex_u.get("saudi_general", {}): E.append(f"المؤشر '{w}' ليس في saudi_general")
        others = [(r2, [w for w in ws if not is_cultural(w)]) for r2, ws in found.items() if r2 in REGIONS]
        others = [x for x in others if x[1]]
        if others: E.append(f"saudi_general لكن السؤال يحوي مفردات إقليمية {others}")
    else:
        if mk != []: E.append("dialect_markers يجب أن تكون [] عند region=none")
        dia = {r2: [w for w in ws if not is_cultural(w)] for r2, ws in found.items()}
        dia = {r2: ws for r2, ws in dia.items() if ws}
        if dia: E.append(f"region=none لكن السؤال يحوي مفردات لهجية من المعجم {dia}: اجعل region مناسبًا أو أزل المفردة")
    # الإجابات
    for a in asst_texts(row):
        if t not in ("rewrite", "summarize") and DIALECT_IN_ANSWER.search(a): E.append(f"مفردة لهجة في الإجابة: {DIALECT_IN_ANSWER.search(a).group(0)}")
        if wc(a) > (120 if is_list(a) else 60): E.append(f"الإجابة {wc(a)} كلمة (الحد 60، وللقوائم 120)")
        elif wc(a) > 60 and is_list(a) is False: E.append("طويلة")
        for p in POLICY_RE:
            mm = p.search(a)
            if mm and norm(mm.group(0)) not in norm(users) and not (re.search(r"\d", mm.group(0)) and re.search(r"\d+", mm.group(0)).group(0) in users): E.append(f"نمط اختراع سياسة/حالة: «{mm.group(0)}»")
    if t == "arithmetic":
        probs, n = arithmetic_problems(m[0]["content"], last_a(row))
        if probs: E.append(f"حسابيات خاطئة: {probs[:2]}")
    if t == "text_answerable" and norm(last_a(row)) not in norm(users): E.append("إجابة text_answerable ليست مقتبسة من النص")
    if t == "text_unanswerable" and not re.search(r"(النص|الفقرة)", last_a(row)): E.append("رفض text_unanswerable لا يستند إلى النص")
    return E
