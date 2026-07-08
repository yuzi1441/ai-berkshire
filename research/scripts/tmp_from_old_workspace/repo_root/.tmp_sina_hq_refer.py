import requests
headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'}
for url in ['https://hq.sinajs.cn/list=sh688235','http://hq.sinajs.cn/list=sh688235','https://hq.sinajs.cn/?list=sh688235','https://hq.sinajs.cn/rn=1&list=sh688235,hk06160,gb_onc']:
    try:
        r=requests.get(url,headers=headers,timeout=20)
        r.encoding='gb18030'
        print('\n',url,r.status_code,r.text[:500])
    except Exception as e: print('ERR',url,e)