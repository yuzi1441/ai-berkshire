from pathlib import Path
for name in ['长江电力-financial-analyst-20260707.md','长江电力-business-analyst-商业模式护城河分析-20260707.md','industry-researcher_长江电力_水电电力行业分析_2026-07-07.md']:
 p=Path(name)
 print('\n===== ', name, p.exists(), p.stat().st_size if p.exists() else None, '====')
 if p.exists():
  t=p.read_text(encoding='utf-8')
  # print selected snippets around key terms
  for key in ['核心结论','总体结论','三情景','安全边际','评分','数据交叉验证']:
   i=t.find(key)
   if i>=0:
    print('\n--', key, '--')
    print(t[max(0,i-800):min(len(t),i+2500)])
    break
