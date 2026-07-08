import requests,re,pathlib
url='https://stockanalysis.com/stocks/onc/financials/'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code,len(r.text),r.url)
print(r.text[:500])
pathlib.Path('sources/sec_beone/stockanalysis_onc_financials.html').write_text(r.text,encoding='utf-8')
for pat in ['Revenue','Net Income','2025','5,343','1,513']:
    i=r.text.find(pat)
    print(pat,i,r.text[i-200:i+500].replace('\n',' ')[:800] if i!=-1 else '')