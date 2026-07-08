import requests,re
for code in ['sz000682','sz000400','sh600406','sh600131','sh601126','sz002270']:
 r=requests.get(f'https://qt.gtimg.cn/q={code}',headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 m=re.search(r'="(.*)"',r.text)
 parts=m.group(1).split('~') if m else []
 print('\n',code,len(parts))
 for i,v in enumerate(parts[:90]):
     print(i,v)
