import requests, re
from pathlib import Path
url='https://www.icbc-ltd.com/column/1438058343653851145.html'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
text=r.content.decode('utf-8','replace')
Path('_icbc_finreports_cn.html').write_text(text,encoding='utf-8')
for m in re.finditer(r'\{[^{}]*?(?:2025|2026|第一季度|年度报告)[^{}]*?\}', text):
 s=m.group(0)
 if any(k in s for k in ['2025','2026','第一季度','年度报告','AnnualReport']): print(s)