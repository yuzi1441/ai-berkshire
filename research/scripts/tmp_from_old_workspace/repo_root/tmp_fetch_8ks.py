import requests, re
from bs4 import BeautifulSoup
from pathlib import Path
headers={'User-Agent':'codex-research whatn@example.com'}
files={
'2026_q1_8k':'https://www.sec.gov/Archives/edgar/data/1651308/000162828026030866/bgne-20260506.htm',
'2025_results_8k':'https://www.sec.gov/Archives/edgar/data/1651308/000162828026011941/bgne-20260226.htm',
'2026_june_8k':'https://www.sec.gov/Archives/edgar/data/1651308/000165130826000017/bgne-20260611.htm',
'2026_june26_8k':'https://www.sec.gov/Archives/edgar/data/1651308/000165130826000020/bgne-20260626.htm'
}
base=Path('sources/beigene_management')
for name,url in files.items():
 r=requests.get(url,headers=headers,timeout=30)
 print(name,r.status_code,len(r.text))
 (base/f'{name}.html').write_text(r.text,encoding='utf-8')
 text=BeautifulSoup(r.text,'html.parser').get_text('\n')
 text=re.sub(r'\n\s*\n+','\n',text)
 (base/f'{name}.txt').write_text(text,encoding='utf-8')
 print(text[:1000])
