import requests, re, json
codes=['sh600900','sh600025','sh600886','sh600795','sh600011','sz003816']
s=requests.Session(); s.trust_env=False
url='https://qt.gtimg.cn/q='+','.join(codes)
r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
r.encoding='gbk'
print(r.text)
for part in r.text.strip().split(';'):
    if '="' not in part: continue
    q=part.split('="',1)[1].rstrip('"')
    f=q.split('~')
    if len(f)>50:
        print(f[1], f[2], 'price',f[3],'chg%',f[32],'pe',f[39],'mcap_yi',f[45],'pb',f[46],'time',f[30], 'shares', f[70] if len(f)>70 else '')
