import requests, re
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0'}
for kw in ['华明装备 2026年第一季度报告 新浪财经','华明装备 2024年年度报告 新浪财经','华明装备 2023年年度报告 新浪财经','华明装备 2022年年度报告 新浪财经','华明装备 2021年年度报告 新浪财经']:
    url='https://www.baidu.com/s?wd='+requests.utils.quote(kw)
    try:
        r=s.get(url,headers=headers,timeout=20)
        print('\nKW',kw,'status',r.status_code,'len',len(r.text))
        for m in re.finditer(r'vCB_AllBulletinDetail\.php\?id=(\d+)&amp;stockid=002270', r.text):
            print('id',m.group(1))
    except Exception as e: print('ERR',e)
