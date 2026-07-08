import requests
from bs4 import BeautifulSoup
urls=[
('annual','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12081234&stockid=000400'),
('q1','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12081227&stockid=000400'),
('summary','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12081214&stockid=000400'),
]
headers={'User-Agent':'Mozilla/5.0'}
for name,u in urls:
    r=requests.get(u,headers=headers,timeout=20)
    print('---',name,r.status_code,r.encoding,r.apparent_encoding,len(r.content))
    r.encoding=r.apparent_encoding or 'gbk'
    text=r.text
    print(text[:500].replace('\n',' ') )
    open(f'tmp_{name}.html','w',encoding='utf-8').write(text)
    soup=BeautifulSoup(text,'html.parser')
    visible=soup.get_text('\n')
    open(f'tmp_{name}.txt','w',encoding='utf-8').write(visible)
    print('saved', f'tmp_{name}.txt', len(visible))