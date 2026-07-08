import urllib.request, urllib.parse, json
urls=[
 'https://np-anotice-stock.eastmoney.com/api/security/ann?cb=&sr=-1&page_size=10&page_index=1&ann_type=A&client_source=web&stock_list=688235',
 'https://datacenter-web.eastmoney.com/api/data/v1/get?sortColumns=REPORT_DATE&sortTypes=-1&pageSize=5&pageNumber=1&reportName=RPT_LICO_FN_CPD&columns=ALL&filter=(SECURITY_CODE="688235")'
]
for url in urls:
    print('\nURL',url)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://data.eastmoney.com/'})
        raw=urllib.request.urlopen(req,timeout=20).read().decode('utf-8','ignore')
        print(raw[:2000])
    except Exception as e: print('ERR',type(e).__name__,e)
