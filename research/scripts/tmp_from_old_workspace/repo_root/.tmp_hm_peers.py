import requests, re, json, pathlib
codes={'华明装备':'sz002270','思源电气':'sz002028','国电南瑞':'sh600406','特变电工':'sh600089','中国西电':'sh601179','许继电气':'sz000400'}
s=requests.Session(); s.trust_env=False
rows=[]
for name,q in codes.items():
    r=s.get('https://qt.gtimg.cn/q='+q,headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'},timeout=20)
    txt=r.content.decode('gbk','ignore')
    m=re.search(r'="(.*)"',txt)
    arr=m.group(1).split('~') if m else []
    # Tencent fields based on observed: 3 price, 38 marketcap? 39 circulation? 44 turnover, 45 PE dynamic? 46? 47 PB? 49 high52? 50 low52?
    row={'name':name,'code':q,'raw':txt[:500]}
    for idx in [3,4,5,31,32,38,39,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62]:
        if idx < len(arr): row[f'f{idx}']=arr[idx]
    rows.append(row)
print(json.dumps(rows,ensure_ascii=False,indent=2))
path=pathlib.Path('reports/华明装备/sources/peer_quotes_tencent.json'); path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
