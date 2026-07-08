from bs4 import BeautifulSoup
from pathlib import Path
html=Path('sources/sec_beone/stockanalysis_onc_financials.html').read_text(encoding='utf-8')
soup=BeautifulSoup(html,'html.parser')
# Find main financial table rows text concise
rows=[]
for tr in soup.find_all('tr'):
    cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])]
    if cells and any(x in cells[0] for x in ['Revenue','Gross Profit','Operating Income','Net Income','EPS','Shares Outstanding','EBITDA','Free Cash Flow']):
        rows.append(cells[:8])
print(rows[:30])