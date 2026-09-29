# -*- coding: utf-8 -*-
"""أدوات مشتركة: تطبيع، كشف لهجة، تصنيف المهام، كتابة على دفعات."""
import json, re, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "build_log.txt")
BATCH = 50

AR = r"؀-ۿ"
def wb(words):
    """نمط كلمات كاملة بحدود عربية."""
    return re.compile(r"(?<![%s])(?:%s)(?![%s])" % (AR, "|".join(words), AR))

# مؤشرات غير سعودية (ممنوعة في كل الملفات)
NON_SAUDI = ["كده", "دلوقتي", "ازاي", "إزاي", "عايز", "عايزة", "هلأ", "هلق", "شو", "بدي", "كتير", "مش"]
NON_SAUDI_RE = wb(NON_SAUDI)

# مؤشرات لهجة عامة (تُمنع في إجابات الفصحى)
DIALECT_ANS = ["وش", "ايش", "إيش", "أبغى", "ابغى", "ابي", "بيتم", "بنراجع", "بنتحقق", "بيضاف", "بنرجع",
               "بنعوضك", "بنرسل", "بنرتب", "بنشحنها", "بنشحن", "بنتابع", "بنحل", "بتحقق", "بيوصل", "بتقدر",
               "زي", "شي", "شوي", "كويس", "تبغى", "تبي", "ودي", "ودك", "أسوي", "اسوي", "يبي", "ليش", "ليه", "وين", "زين",
               "عشان", "علشان", "ما أقدر", "ما أملك", "ما أستطيع", "ما عندي", "قول لي", "ناوي", "بدري", "هالحين",
               "دحين", "دايم", "دايمًا", "مره", "كذا", "هذي", "هذا الشي", "اللي", "مو", "ماني", "لين",
               "حبيت", "هالشي", "هذي", "لازم", "قدك", "تقدر", "أقدر", "أشوف", "أعطيك", "تلقى", "خلها",
               "أحس", "تحس", "بس", "حياك", "مشكور", "الله يعافيك", "أبشر", "طيب", "يالله", "هيه", "وشلون", "شلون"]
DIALECT_ANS_RE = wb(sorted(set(DIALECT_ANS), key=len, reverse=True))

def strip_tashkeel(s):
    return re.sub(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]", "", s)

def norm(s):
    """تطبيع الهمزات والتشكيل والترقيم لمقارنة التداخل."""
    s = strip_tashkeel(s)
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    s = re.sub("[أإآٱ]", "ا", s)
    s = s.replace("ؤ", "و").replace("ئ", "ي").replace("ى", "ي").replace("ة", "ه").replace("ء", "")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()

def wc(s):
    return len(s.split())

REFUSAL_START = re.compile(r"^(لا (أملك|أستطيع|يمكنني|يمكن|أقدر|أعرف|يوجد|أجد|أتوفر|تتوفر|أحتفظ|أطلع|أستقبل|أحلل)|ما (أقدر|أملك|أستطيع|يمكنني)|النص لا|لم يرد|لا تتضمن|أعتذر|تختلف الإجابة|قد تتغير|تتغير الأفضلية|لا يجوز)")

def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def log(msg):
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("[%s] %s\n" % (ts, msg))

class BatchWriter:
    """يكتب JSONL على دفعات لا تزيد على 50 صفًا ويسجل كل دفعة في build_log.txt."""
    def __init__(self, path, label):
        self.path, self.label = path, label
        self.buf, self.n, self.batches = [], 0, 0
        open(path, "w", encoding="utf-8").close()
    def add(self, obj):
        self.buf.append(obj)
        if len(self.buf) >= BATCH:
            self.flush()
    def flush(self):
        if not self.buf:
            return
        with open(self.path, "a", encoding="utf-8") as f:
            for o in self.buf:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        self.n += len(self.buf)
        self.batches += 1
        log("%s: دفعة %d محفوظة (%d صفًا، الإجمالي %d)" % (self.label, self.batches, len(self.buf), self.n))
        self.buf = []
    def close(self):
        self.flush()
        log("%s: اكتمل الكتابة، %d صفًا في %d دفعة" % (self.label, self.n, self.batches))
        return self.n

def row(q, a, typ, region="none"):
    return {"messages": [{"role": "user", "content": q}, {"role": "assistant", "content": a}],
            "meta": {"type": typ, "region": region}}

def task_type(q, a):
    """تصنيف تقريبي لنوع المهمة بالقواعد (يعتمد على أول كلمات السؤال)."""
    first = q.split("\n")[0].strip()
    if "بحسب السياق" in a and "ثانياً" in a: return "compare"
    if re.search(r"(في بايثون|لغة بايثون|لبايثون)", q) and not first.startswith("لخّص"): return "python"
    if re.match(r"^(ترجم)", first) or "Free delivery" in q: return "translation"
    if REFUSAL_START.search(a[:40]): return "refusal"
    if re.match(r"^(لخص|لخّص|أوجز|اختصر|أعطني ملخص|ما خلاصة|اكتب خلاصة|اكتب ملخص|حوّل النص إلى ملخص|ما ملخص)", first): return "summarize"
    if re.match(r"^(استخرج|طلّع|صنف|صنّف|حدد|ما الفكرة)", first): return "extract"
    if re.match(r"^(أعد|حوّل|حول |صحح|صحّح|انقل|صغ|خلّ|أزل|اكتب رد|اكتب ردًا|بدّل|عدّل|الجملة التالية)", first) and not re.search(r"\d+\s*(ريال|دولار|يورو|درجة|كيلو|دينار|جنيه)", first): return "rewrite"
    if re.search(r"\d", q) and re.search(r"(ريال|دولار|%|احسب|كم يمثل|كم يعادل|كم تبلغ|نسبة|إجمالي|صافي|هامش)", q): return "arithmetic"
    if re.search(r"(أفعل|أتعامل|أحافظ|أبدأ|أنظم|أتخلص|أكون|أتغلب|أحسن|أختار|أوفر|أخفض|أطور|أتعلم|أشرح|أتجنب|أقلل|أحسّن|نصيحة|تنصحني|أستعد|أجعل)", first): return "advice"
    return "informational"


# مؤشرات لهجية في سؤال المستخدم (تُستعمل للتأكد أن أسئلة اللهجات ليست فصحى خالصة)
DIA_Q = re.compile(r"(?<![\u0600-\u06FF])[وفبل]?(?:وش|ايش|أبغى|ابغى|ابي|ودي|ليش|ليه|وين|شلون|الحين|هالحين|دحين|مرة|تكفى|هالرسالة|هالنص|هالجملة|"
                   r"هالتقرير|مين|حق|شي|شوي|اللي|مب|مو|بكرة|لين|أسوي|أسويه|تبغى|يبغى|بغيت|عشان|زين|يعطيك|هلا|ياخي|قول|ما أقدر|بروح|بتأخر|بعد بكرة|"
                   r"دايم|مره|كذا|هذي|هالحين|ياخي|والله|يا شيخ)(?![\u0600-\u06FF])")
