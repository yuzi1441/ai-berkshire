import requests, json, pathlib, csv, time
symbols=['2383.TW','6213.TW','6274.TWO','3037.TW','2313.TW','8046.TW','2368.TW','4958.TW','TTMI','ROG','ATS.VI','4062.T','6787.T','1488.HK','1888.HK','2802.T','4182.T']
headers={'User-Agent':'Mozilla/5.0'}
rows=[]; raw={}
for sym in symbols:
    try:
        qurl=f'https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym}'
        qr=requests.get(qurl,headers=headers,timeout=15)
        print(sym, qr.status_code, qr.text[:60])
        q=qr.json().get('quoteResponse',{}).get('result',[])
        item=q[0] if q else {}
        rows.append({k:item.get(k) for k in ['symbol','shortName','regularMarketPrice','regularMarketChangePercent','marketCap','trailingPE','forwardPE','priceToBook','currency','regularMarketTime','fiftyTwoWeekHigh','fiftyTwoWeekLow']})
        raw[sym]=item
        time.sleep(0.2)
    except Exception as e:
        print(sym,'ERR',repr(e)); raw[sym]={'error':repr(e)}
pathlib.Path('data/ai-pcb-materials').mkdir(parents=True,exist_ok=True)
pathlib.Path('data/ai-pcb-materials/yahoo_quote_raw_20260710.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
if rows:
    keys=['symbol','shortName','regularMarketPrice','regularMarketChangePercent','marketCap','trailingPE','forwardPE','priceToBook','currency','regularMarketTime','fiftyTwoWeekHigh','fiftyTwoWeekLow']
    with open('data/ai-pcb-materials/yahoo_quote_snapshot_20260710.csv','w',newline='',encoding='utf-8-sig') as fp:
        w=csv.DictWriter(fp,fieldnames=keys); w.writeheader(); w.writerows(rows)
    print(json.dumps(rows,ensure_ascii=False,indent=2)[:10000])
