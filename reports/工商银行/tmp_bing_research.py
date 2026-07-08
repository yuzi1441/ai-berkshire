import requests, re
from bs4 import BeautifulSoup
queries=['张红力 工商银行 原副行长 受贿 判决 2025 官方','国家金融监督管理总局 工商银行 行政处罚 2025 工商银行','工商银行 消费者权益保护 投诉 2025 年报']
headers={'User-Agent':'Mozilla/5.0'}
for q in queries:
    print('\nQUERY', q)
    url='https://www.bing.com/search?q='+requests.utils.quote(q)
    r=requests.get(url,headers=headers,timeout=15)
    print(r.status_code, r.url, len(r.text))
    soup=BeautifulSoup(r.text,'html.parser')
    for li in soup.select('li.b_algo')[:5]:
        a=li.find('a')
        if a:
            print(a.get_text(' ',strip=True), a.get('href'))
            p=li.find('p')
            if p: print(' ',p.get_text(' ',strip=True)[:250])