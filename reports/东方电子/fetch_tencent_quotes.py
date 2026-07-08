import requests
for code in ['sz000682','sz000400','sh600406','sh600131','sh601567','sz002339']:
    try:
        r=requests.get('https://qt.gtimg.cn/q='+code,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
        # decode try gbk
        txt=r.content.decode('gbk','ignore')
        print('\nTENCENT',code,r.status_code,txt[:800])
    except Exception as e:
        print('ERR',code,repr(e))
