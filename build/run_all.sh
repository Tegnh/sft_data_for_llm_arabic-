#!/usr/bin/env bash
# يعيد بناء كل المخرجات من الملفين الأصليين: bash build/run_all.sh
set -e
cd "$(dirname "$0")/.."
rm -f build_log.txt
for s in audit clean_train gen_dialect gen_pairs assemble_train gen_val_test make_review_sample post_summary; do python3 build/$s.py > /dev/null; done
set +e
python3 check_sft.py > check_sft_output.txt 2>&1
code=$?
python3 -c "import sys; sys.path.insert(0,'build'); from common import log; log('check_sft.py: رمز الخروج = $code (0 = نجحت كل الفحوص الإلزامية)')"
tail -4 check_sft_output.txt
exit $code
