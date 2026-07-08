from bs4 import BeautifulSoup
html=open('reports/工商银行/_tmp_bing.html',encoding='utf-8').read()
soup=BeautifulSoup(html,'html.parser')
for li in soup.select('li.b_algo')[:10]:
 a=li.find('a')
 print('TITLE', a.get_text(' ',strip=True) if a else None)
 print('HREF', a.get('href') if a else None)
 print('SNIP', li.get_text(' ',strip=True)[:300])
 print()