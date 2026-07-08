import requests, os, re, json
headers={'User-Agent':'whatn research whatn@example.com','Accept-Encoding':'gzip, deflate'}
base='https://www.sec.gov/Archives/edgar/data/1651308/{acc}/{doc}'
filings={
 '2025_10k':'000162828026011946/bgne-20251231.htm',
 '2026_q1_10q':'000162828026030867/bgne-20260331.htm',
 '2026_q1_8k':'000162828026030866/bgne-20260506.htm',
 '2025_8k_results':'000162828026011941/bgne-20260226.htm',
}
os.makedirs('sources/sec',exist_ok=True)
for name,path in filings.items():
    url='https://www.sec.gov/Archives/edgar/data/1651308/'+path
    r=requests.get(url,headers=headers,timeout=30)
    print(name,r.status_code,len(r.text),url)
    open(f'sources/sec/{name}.html','w',encoding='utf-8').write(r.text)
    # list exhibits links
    links=re.findall(r'href="([^"]+)"[^>]*>([^<]+)', r.text, re.I)
    for href,text in links[:30]:
        if 'ex' in href.lower() or 'exhibit' in text.lower(): print(' ',href,text[:80])