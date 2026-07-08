from bs4 import BeautifulSoup
text=open('_icbc_finreports.html',encoding='utf-8').read()
soup=BeautifulSoup(text,'html.parser')
for a in soup.find_all('a'):
    t=' '.join(a.get_text(' ',strip=True).split())
    href=a.get('href') or ''
    if t or href:
        print(repr(t),'=>',href)