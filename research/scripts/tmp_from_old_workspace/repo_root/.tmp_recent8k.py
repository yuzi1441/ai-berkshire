from bs4 import BeautifulSoup
from pathlib import Path
import urllib.request,re
headers={'User-Agent':'codex research contact@example.com'}
for name,path in {'2026_0626_8K':'000165130826000020/bgne-20260626.htm','2026_0611_8K':'000165130826000017/bgne-20260611.htm','2026_0513_8K':'000165130826000012/bgne-20260513.htm'}.items():
    url='https://www.sec.gov/Archives/edgar/data/1651308/'+path
    try:
        data=urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=20).read()
        p=Path('sources/sec_beone')/(name+'.html'); p.write_bytes(data)
        text=BeautifulSoup(data,'html.parser').get_text('\n')
        print('\n###',name,url)
        print(re.sub(r'\n{2,}','\n',text[:2500]))
    except Exception as e: print('ERR',name,e)