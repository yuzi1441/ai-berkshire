import requests,re, pathlib
pages={
'sina_a_page':'https://finance.sina.com.cn/realstock/company/sh688235/nc.shtml',
'sina_us_page':'https://stock.finance.sina.com.cn/usstock/quotes/ONC.html',
'sina_hk_page':'https://stock.finance.sina.com.cn/hkstock/quotes/06160.html',
}
for name,url in pages.items():
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
    enc='gb18030' if 'sina' in url else r.encoding
    txt=r.content.decode(enc,errors='ignore')
    pathlib.Path(f'sources/sec_beone/{name}.html').write_text(txt,encoding='utf-8')
    print('\n###',name)
    for pat in ['最新价','当前价','昨收','市值','总市值','309','277','190.5','Market Cap','price']:
        i=txt.find(pat)
        print(pat,i)
        if i!=-1: print(re.sub(r'\s+',' ',txt[i-250:i+450])[:900])