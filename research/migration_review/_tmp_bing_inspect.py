import requests, re
s=requests.Session(); s.trust_env=False
r=s.get('https://cn.bing.com/search',params={'q':'工商银行 2025 年度报告 pdf','count':10},headers={'User-Agent':'Mozilla/5.0'},timeout=20)
open('reports/工商银行/_tmp_bing.html','w',encoding='utf-8').write(r.text)
print(len(r.text))
for pat in ['b_algo','icbc','工商银行','href=']:
 print(pat, r.text.find(pat))
print(r.text[:1000])