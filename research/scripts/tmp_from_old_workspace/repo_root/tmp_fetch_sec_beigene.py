import requests, re, html
from pathlib import Path
from bs4 import BeautifulSoup
headers={'User-Agent':'codex-research whatn@example.com'}
base=Path('sources/beigene_management')
base.mkdir(parents=True, exist_ok=True)
filings={
 '2025_10k':'https://www.sec.gov/Archives/edgar/data/1651308/000162828026011946/bgne-20251231.htm',
 '2026_q1_10q':'https://www.sec.gov/Archives/edgar/data/1651308/000162828026030867/bgne-20260331.htm',
 '2026_proxy':'https://www.sec.gov/Archives/edgar/data/1651308/000110465926049655/tm261479-4_def14a.htm',
 '2024_10k':'https://www.sec.gov/Archives/edgar/data/1651308/000165130825000031/bgne-20241231.htm',
 '2023_10k':'https://www.sec.gov/Archives/edgar/data/1651308/000165130824000014/bgne-20231231.htm',
}
for name,url in filings.items():
    r=requests.get(url,headers=headers,timeout=30)
    print(name, r.status_code, len(r.text), url)
    (base/f'{name}.html').write_text(r.text,encoding='utf-8')
    soup=BeautifulSoup(r.text,'html.parser')
    text=soup.get_text('\n')
    text=re.sub(r'\n\s*\n+', '\n', text)
    (base/f'{name}.txt').write_text(text,encoding='utf-8')
print(base.resolve())
