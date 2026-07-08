import requests, pathlib, json, re
headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}
urls={
 'sina':'https://hq.sinajs.cn/list=sz000682',
 'tencent':'https://qt.gtimg.cn/q=sz000682',
 'tencent_kline':'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000682,day,,,5,qfq'
}
raw={}
for k,u in urls.items():
    r=requests.get(u,headers=headers,timeout=15)
    r.encoding='GB18030' if k in ['sina','tencent'] else 'utf-8'
    raw[k]=r.text
path=pathlib.Path.cwd()/'source_docs'/'quotes_000682_20260707.json'
path.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
print(path)
# parse concise
sina=raw['sina'].split('="',1)[1].split('";',1)[0].split(',')
tq=raw['tencent'].split('="',1)[1].split('";',1)[0].split('~')
print('sina name open prev close high low volume amount date time',sina[0],sina[1],sina[2],sina[3],sina[4],sina[5],sina[8],sina[9],sina[30],sina[31])
print('tencent name code price prev open high low volume amount turnover pe? mcap/liquidity?',tq[1],tq[2],tq[3],tq[4],tq[5],tq[33],tq[34],tq[36],tq[37],tq[38],tq[39],tq[45],tq[44],tq[46])
