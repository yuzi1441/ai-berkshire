import requests,re
for id in ['12310579','11922323','11834400']:
 url=f'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id={id}&stockid=002028'
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 r.encoding='gbk'
 print('\nID',id,'status',r.status_code,'len',len(r.text))
 print(r.text[:500])
 for m in re.finditer(r'href="([^"]+)"', r.text):
  href=m.group(1)
  if 'PDF' in href.upper() or 'download' in href.lower() or 'static' in href:
   print('href',href)
 print('pdf direct', re.findall(r'https?://[^"\']+?\.PDF', r.text, flags=re.I)[:5])