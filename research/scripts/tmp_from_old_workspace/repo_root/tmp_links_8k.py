from pathlib import Path
from bs4 import BeautifulSoup
for fname in ['2025_results_8k.html','2026_q1_8k.html']:
 soup=BeautifulSoup(Path('sources/beigene_management/'+fname).read_text(encoding='utf-8'),'html.parser')
 print('\n====',fname,'links====')
 for a in soup.find_all('a'):
  print(a.get_text(' ',strip=True), a.get('href'))
 print('\nexhibits?')
 for term in ['ex991','exhibit99','d','EX-99']:
  print(term, str(soup).lower().find(term.lower()))
