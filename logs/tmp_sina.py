import requests, re, pathlib, json
url='https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12027374&stockid=600372'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code, r.url, r.encoding, len(r.text))
text=r.text
print(text[:1000])
for m in re.finditer(r'https?://[^\"\']+?\.pdf', text, re.I): print('PDF',m.group(0))