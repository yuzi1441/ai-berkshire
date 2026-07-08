import requests, re
from bs4 import BeautifulSoup
from pathlib import Path
headers={'User-Agent':'codex-research whatn@example.com'}
baseurl='https://www.sec.gov/Archives/edgar/data/1651308/'
exhibits={
'2025_results_pr':'000162828026011941/exhibit991-q42025earningsr.htm',
'2026_q1_pr':'000162828026030866/exhibit991-q12026earningsr.htm'
}
base=Path('sources/beigene_management')
for name,path in exhibits.items():
 url=baseurl+path
 r=requests.get(url,headers=headers,timeout=30)
 print(name,r.status_code,len(r.text),url)
 (base/f'{name}.html').write_text(r.text,encoding='utf-8')
 text=BeautifulSoup(r.text,'html.parser').get_text('\n')
 text=re.sub(r'\n\s*\n+','\n',text)
 (base/f'{name}.txt').write_text(text,encoding='utf-8')
 for term in ['John V. Oyler','Aaron Rosenberg','Total revenue','BRUKINSA','2026 Financial Guidance','GAAP operating income','profitability','self-funding']:
  idx=text.lower().find(term.lower())
  print(' ',term,idx, text[max(0,idx-200):idx+700].replace('\n',' ')[:900] if idx!=-1 else '')
