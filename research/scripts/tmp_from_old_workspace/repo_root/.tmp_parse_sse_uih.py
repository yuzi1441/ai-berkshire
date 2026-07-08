import json,re, pathlib
text=pathlib.Path('sources/联影医疗/sse_query.txt').read_text(encoding='utf-8')
js=re.search(r'jsonpCallback\d+\((.*)\)$', text).group(1)
data=json.loads(js)
for d in data['pageHelp']['data'][:10]:
 print(d['SSEDATE'], d['TITLE'], 'https://www.sse.com.cn'+d['URL'])
