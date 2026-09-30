"""qa_merge.py — يقرأ qa/out/qa_NNN.verdict.jsonl (سطر لكل صف فاشل: {"idx":i,"reasons":[...]}) ويكتب qa/failed_ids.json + حكم pass لبقية الصفوف"""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(__file__))
import v3lib as L
failed = []; total = 0
for f in sorted(glob.glob(os.path.join(L.V3, "qa", "in", "qa_*.jsonl"))):
    n = os.path.basename(f)[3:6]; rows = L.load_jsonl(f)
    vp = os.path.join(L.V3, "qa", "out", f"qa_{n}.verdict.jsonl")
    bad = {}
    if os.path.exists(vp):
        for l in L.load_jsonl(vp): bad[l["idx"]] = l.get("reasons", [])
    out = []
    for i, r in enumerate(rows):
        total += 1
        if i in bad: failed.append({"qa_id": r["qa_id"], "reasons": bad[i]}); out.append({"qa_id": r["qa_id"], "verdict": "fail", "reasons": bad[i]})
        else: out.append({"qa_id": r["qa_id"], "verdict": "pass", "reasons": []})
    L.write_jsonl(os.path.join(L.V3, "qa", "out", f"qa_{n}.full.jsonl"), out)
json.dump([x["qa_id"] for x in failed], open(os.path.join(L.V3, "qa", "failed_ids.json"), "w"))
json.dump(failed, open(os.path.join(L.V3, "qa", "failed_detail.json"), "w"), ensure_ascii=False, indent=1)
print("راجعتُ", total, "صفًا؛ فشل", len(failed))
