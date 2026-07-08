from pathlib import Path
text=Path('sources/sse_2026Q1.txt').read_text(encoding='utf-8', errors='ignore')
for pat in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','基本每股收益']:
 idx=text.find(pat)
 print('\n--',pat,idx,'--')
 print(text[max(0,idx-300):idx+1000].replace('\n',' '))
