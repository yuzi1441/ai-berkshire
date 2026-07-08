import requests,json,re,pathlib
out=pathlib.Path('reports/中国神华/sources'); out.mkdir(exist_ok=True,parents=True)
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?jsonCallBack=jsonpCallback&isPagination=true&productId=601088&keyWord=运营数据&securityType=0101,120100,020100,020200,120200&reportType=ALL&beginDate=2026-01-01&endDate=2026-07-07&pageHelp.pageSize=30&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'},timeout=30)
text=r.text
m=re.search(r'jsonpCallback\((.*)\)$',text,re.S)
data=json.loads(m.group(1))
items=data['pageHelp']['data']
print(len(items))
for it in items[:20]: print(it['SSEDATE'],it['TITLE'],it['URL'])
(out/'sse_ops_announcements.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
