import requests, re
urls=[
 'https://www.icbc-ltd.com/column/1438058343653851145.html',
 'https://www.icbc-ltd.com/ICBCLtd/Investor%20Relations/Financial%20Information/Financial%20Reports/default.htm',
 'https://www.icbc-ltd.com/ICBCLtd/%E6%8A%95%E8%B5%84%E8%80%85%E5%85%B3%E7%B3%BB/%E8%B4%A2%E5%8A%A1%E4%BF%A1%E6%81%AF/%E8%B4%A2%E5%8A%A1%E6%8A%A5%E5%91%8A/default.htm',
]
for u in urls:
    try:
        r=requests.get(u,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
        print('\nURL',u,'status',r.status_code,'len',len(r.content),'ct',r.headers.get('content-type'))
        print(r.text[:500])
    except Exception as e: print('ERR',u,e)