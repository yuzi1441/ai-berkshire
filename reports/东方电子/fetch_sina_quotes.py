import requests, re
codes=['sz000682','sz000400','sh600406','sh600131','sh601567','sz002339']
for code in codes:
    try:
        r=requests.get('https://hq.sinajs.cn/list='+code,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=20)
        r.encoding='gbk'
        print('\nSINA',code,r.status_code)
        print(r.text[:500])
    except Exception as e:
        print('ERR',code,repr(e))
