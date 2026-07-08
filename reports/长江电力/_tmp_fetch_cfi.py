import requests
url='https://www.cfi.net.cn/p20260706001317.html'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code, r.encoding, len(r.content))
text=r.content.decode(r.apparent_encoding or 'utf-8','ignore')
print(text[:1000])
open('sources/cfi_2026_h1_power.html','w',encoding='utf-8').write(text)
for key in ['发电量','三峡','上半年','亿千瓦时','公告']:
    idx=text.find(key)
    print('\nKEY',key,idx)
    print(text[max(0,idx-400):idx+1200] if idx>=0 else '')