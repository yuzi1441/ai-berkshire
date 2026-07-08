import requests,re
url='https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1260352&itemId=4113'
r=requests.get(url,timeout=20); r.encoding='utf-8'
for m in re.finditer(r'(?:api|rest|ItemDetail|docId|ajax|/cn/)[^"\']+', r.text):
 print(m.group(0)[:200])
