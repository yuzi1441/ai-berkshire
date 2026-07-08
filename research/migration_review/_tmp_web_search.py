import requests, re, json
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0'}
queries=[
 '工商银行 2025 年度报告 pdf',
 '工商银行 2026 第一季度报告 pdf',
 'site:v.icbc.com.cn/userfiles/resources/icbcltd/download/2026 工商银行 2025 年度报告 pdf',
]
for q in queries:
 print('\nQUERY',q)
 url='https://www.bing.com/search'
 r=s.get(url,params={'q':q,'count':10},headers=headers,timeout=20)
 print(r.status_code, r.url, r.text[:100])
 for m in re.finditer(r'<a href="(https?://[^"]+)"[^>]*>(.*?)</a>', r.text):
  href=m.group(1); title=re.sub('<.*?>','',m.group(2))
  if any(x in href.lower() for x in ['icbc','cninfo','sse','pdf']) or '工商' in title:
   print(title[:100], href[:300])