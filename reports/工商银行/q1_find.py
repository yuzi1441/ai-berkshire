from pathlib import Path
text = Path('Announce20260429_5.txt').read_text(encoding='utf-8')
for pat in ['经营情况','经营情况简析','实现净利润','计提各类资产减值']:
    print(pat, text.find(pat))
    i=text.find(pat)
    if i!=-1: print(text[i-800:i+2200])
