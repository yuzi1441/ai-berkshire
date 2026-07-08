import requests, pathlib, re
for url in ['https://stockanalysis.com/stocks/onc/statistics/','https://stockanalysis.com/stocks/onc/']:
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
    print(url,r.status_code,len(r.text))
    pathlib.Path('sources/sec_beone/'+url.strip('/').split('/')[-1]+'_stockanalysis.html').write_text(r.text,encoding='utf-8')
    for pat in ['Market Cap','Enterprise Value','PE Ratio','PS Ratio','309.','34.']:
        i=r.text.find(pat); print(pat,i,r.text[i-200:i+400].replace('\n',' ')[:700] if i!=-1 else '')