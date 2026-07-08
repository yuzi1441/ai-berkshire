from pathlib import Path
import re
s = Path('_tmp_sina_q1.html').read_bytes().decode('gbk','ignore')
print(s[:500])
print('pdf', re.findall(r"https?://[^\"']+?\.PDF|https?://[^\"']+?\.pdf", s)[:10])
print('final/static', re.findall(r"(?:finalpage|static)[^\"']+", s)[:20])
for pat in ['下载公告','PDF','601126','2026']:
    print(pat, s.find(pat))
