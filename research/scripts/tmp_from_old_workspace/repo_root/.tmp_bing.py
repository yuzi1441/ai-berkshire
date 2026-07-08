import requests, re
from bs4 import BeautifulSoup
queries=['华明装备 肖毅 访谈 海外 分接开关','华明装备 投资者关系活动记录表 2025 调研','华明装备 机构调研 2025 杨建琴 肖毅','华明装备 业绩说明会 2025 肖毅','华明装备 调研纪要 2024 海外 特高压']
headers={'User-Agent':'Mozilla/5.0'}
for q in queries:
    print('\nQ',q)
    url='https://www.bing.com/search'
    r=requests.get(url,params={'q':q,'mkt':'zh-CN'},headers=headers,timeout=20)
    print('status',r.status_code,'len',len(r.text))
    soup=BeautifulSoup(r.text,'html.parser')
    for li in soup.select('li.b_algo')[:5]:
        a=li.find('a')
        if a: print(a.get_text(' ',strip=True), a.get('href'))
        p=li.find('p')
        if p: print(' ',p.get_text(' ',strip=True)[:300])