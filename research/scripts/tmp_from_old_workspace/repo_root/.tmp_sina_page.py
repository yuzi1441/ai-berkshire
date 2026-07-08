import requests
urls=['https://finance.sina.com.cn/realstock/company/sh688235/nc.shtml','https://stock.finance.sina.com.cn/usstock/quotes/ONC.html','https://stock.finance.sina.com.cn/hkstock/quotes/06160.html']
for url in urls:
    try:
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
        print('\n',url,r.status_code,len(r.text),r.text[:200])
    except Exception as e: print('ERR',url,e)