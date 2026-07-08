import requests, os
headers={'User-Agent':'whatn research whatn@example.com','Accept-Encoding':'gzip, deflate'}
items={
 '2026_q1_press':'https://www.sec.gov/Archives/edgar/data/1651308/000162828026030866/exhibit991-q12026earningsr.htm',
 '2025_fy_press':'https://www.sec.gov/Archives/edgar/data/1651308/000162828026011941/exhibit991-q42025earningsr.htm',
}
os.makedirs('sources/sec',exist_ok=True)
for name,url in items.items():
    r=requests.get(url,headers=headers,timeout=30)
    print(name,r.status_code,len(r.text))
    open(f'sources/sec/{name}.html','w',encoding='utf-8').write(r.text)