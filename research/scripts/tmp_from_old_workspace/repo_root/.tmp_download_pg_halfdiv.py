import requests, pathlib
url='http://static.cninfo.com.cn/finalpage/2025-10-11/1224704591.PDF'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=30)
print(r.status_code, len(r.content), r.content[:4])
p=pathlib.Path('sources/pinggao/rights2025_half.pdf'); p.write_bytes(r.content)
import pdfplumber
text='\n'.join((pg.extract_text() or '') for pg in pdfplumber.open(p).pages)
pathlib.Path('sources/pinggao/rights2025_half.txt').write_text(text,encoding='utf-8')
print(text[:2500])
