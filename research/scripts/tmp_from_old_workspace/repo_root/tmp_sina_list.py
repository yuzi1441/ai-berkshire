import requests,re
url='https://money.finance.sina.com.cn/corp/go.php/vCB_Bulletin/stockid/601126/page_type/ndbg.phtml'
r=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0'})
print(r.status_code, r.encoding, r.apparent_encoding, len(r.content))
text=r.content.decode(r.apparent_encoding or 'gbk', errors='replace')
for m in re.finditer(r'view/vCB_AllBulletinDetail\.php\?stockid=601126&id=(\d+).*?四方股份：([^<]+)', text, re.S):
    title=m.group(2)
    if '2025年第一季度' in title or '2025年年度' in title or '2026年第一季度' in title:
        print(m.group(1), title[:80])