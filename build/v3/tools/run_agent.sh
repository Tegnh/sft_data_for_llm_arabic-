#!/bin/bash
# usage: run_agent.sh <agent> "<prompt>"  — يشغّل وكيلًا كعملية مستقلة بنموذج claude-sonnet-5-5 وصلاحيات محدودة بمسارات المشروع
cd /home/user/sft_data_for_llm_arabic-
A="$1"; P="$2"
exec claude -p --model claude-sonnet-5-5 --agent "$A" --output-format json \
  --allowedTools "Read" "Glob" "Grep" "Agent" \
    "Write(//home/user/sft_data_for_llm_arabic-/build/v3/**)" "Edit(//home/user/sft_data_for_llm_arabic-/build/v3/**)" \
    "Bash(python3 build/v3/tools/*)" "Bash(python3 check_sft.py*)" "Bash(sleep *)" "Bash(ls *)" "Bash(wc *)" "Bash(cat *)" "Bash(head *)" "Bash(tail *)" "Bash(mkdir -p build/v3/*)" \
  -- "$P" > "build/v3/logs/$A.json" 2> "build/v3/logs/$A.err"
