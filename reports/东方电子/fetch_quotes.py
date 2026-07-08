import requests, json, datetime
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
fields='f43,f44,f45,f46,f47,f48,f57,f58,f60,f86,f116,f117,f162,f167,f168,f169,f170,f173,f187,f105,f115,f127,f128,f129,f130,f131,f132,f133,f134,f135,f136,f137,f138,f139,f140,f141,f142,f143,f144,f145,f146,f147,f148,f149,f150,f151,f152'
for secid in ['0.000682','0.000400','1.600406','1.600131','1.601567','0.002339']:
    url=f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields={fields}'
    r=requests.get(url,headers=headers,timeout=15)
    print('\n',secid,r.status_code)
    d=r.json().get('data')
    print(json.dumps(d,ensure_ascii=False,indent=2)[:2000])
# Sina
for code in ['sz000682','sz000400','sh600406','sh600131']:
    r=requests.get('https://hq.sinajs.cn/list='+code,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=15)
    r.encoding='gbk'
    print('\nSINA',code,r.status_code,r.text[:300])
