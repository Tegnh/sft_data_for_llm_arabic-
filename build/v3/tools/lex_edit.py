import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
names={"nejd":"نجد","hijaz":"الحجاز","south":"الجنوب","east":"الشرق","north":"الشمال","saudi_general":"سعودي عام (مشترك)"}
def save(lex, path=None):
    path = path or os.path.join(L.V3, "dialect_lexicon.md")
    head = open(path, encoding="utf-8").read().split("\n## ")[0].rstrip("\n") + "\n"
    out = [head]
    for r in ["nejd", "hijaz", "south", "east", "north", "saudi_general"]:
        v = lex[r]
        out.append(f"\n## {r}\n\n{names[r]} — {len(v)} مفردة\n\n| مفردة | جملة مثال | ثقة |\n|---|---|---|\n")
        for w, ex, c in v: out.append(f"| {w} | {ex} | {c} |\n")
    open(path, "w", encoding="utf-8").write("".join(out))
def move(lex, word, src, dst, conf=None):
    for i, (w, ex, c) in enumerate(lex[src]):
        if w == word:
            lex[src].pop(i); lex[dst].append((w, ex, conf or c)); return
    raise KeyError(word)
if __name__ == "__main__":
    lex = L.parse_lexicon()
    move(lex, "دحين", "hijaz", "saudi_general", "high")
    for i, (w, ex, c) in enumerate(lex["hijaz"]):
        if w == "عيل": lex["hijaz"][i] = (w, ex, "low")
    lex["east"] += [("أرقد","أرقد بدري وما أقدر أصحى، كيف أضبط نومي","medium"),("أنطر","أنطر الرد من الشركة، كم المدة المعتادة","medium"),
                    ("سالفة","سالفة الأسهم هذي كيف أفهمها","medium"),("هاي","هاي الفكرة كيف أطبقها","medium"),("إنته","إنته تعرف الفرق بين الفيزياء والكيمياء","medium")]
    lex["north"] += [("حيل","حيل مشغول، كيف أنظم وقتي","medium"),("واجد","عندي واجد أسئلة عن الاستثمار","medium")]
    lex["south"] += [("ما شي","ما شي وقت عندي أراجع، كيف أختصر","medium")]
    save(lex)
