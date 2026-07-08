import akshare as ak, pandas as pd, re, requests, pathlib, json, os, sys, time
symbol='002270'
out=pathlib.Path('data/huaming_002270'); out.mkdir(parents=True, exist_ok=True)
sources=pathlib.Path('sources/002270'); sources.mkdir(parents=True, exist_ok=True)
queries=[
 ('report_all_2024_2026','', '', '20240101','20260706'),
 ('annual_2025','2025年年度报告', '年报','20260101','20260706'),
 ('q1_2026','2026年第一季度报告','一季报','20260101','20260706'),
 ('semi_2025','2025年半年度报告','半年报','20250101','20260706'),
 ('q3_2025','2025年第三季度报告','三季报','20250101','20260706'),
]
for name, keyword, cat, start, end in queries:
    print('\n--- cninfo',name,'---')
    try:
        df=ak.stock_zh_a_disclosure_report_cninfo(symbol=symbol, market='沪深京', keyword=keyword, category=cat, start_date=start, end_date=end)
        print('shape',df.shape)
        print(df.head(30).to_string())
        df.to_csv(out/f'cninfo_{name}.csv',index=False,encoding='utf-8-sig')
    except Exception as e:
        print('ERR',type(e).__name__,e)

# read all, download key PDFs
all_path=out/'cninfo_report_all_2024_2026.csv'
if all_path.exists():
    all_df=pd.read_csv(all_path)
else:
    all_df=pd.read_csv(out/'cninfo_report_all_2024_2026.csv') if (out/'cninfo_report_all_2024_2026.csv').exists() else None

if all_df is not None:
    mask=all_df['公告标题'].astype(str).str.contains('2026年第一季度报告|2025年年度报告|2025年半年度报告|2025年三季度报告|2025年第三季度报告|2024年年度报告', regex=True, na=False)
    key=all_df[mask].copy()
    print('\n--- key announcements ---')
    print(key[['代码','简称','公告标题','公告时间','公告链接']].to_string(index=False))
    key.to_csv(out/'key_announcements.csv', index=False, encoding='utf-8-sig')
    for _,r in key.iterrows():
        link=str(r['公告链接']); title=re.sub(r'[\\/:*?"<>|\s]+','_',str(r['公告标题']))[:80]
        m=re.search(r'announcementId=(\d+)', link); aid=m.group(1) if m else None
        date=str(r['公告时间'])[:10]
        if aid and date:
            url=f'http://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF'
            path=sources/f'{date}_{aid}_{title}.pdf'
            try:
                resp=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=30)
                print('download',title, resp.status_code, resp.headers.get('content-type'), len(resp.content), url)
                if resp.status_code==200 and len(resp.content)>1000:
                    path.write_bytes(resp.content)
            except Exception as e: print('download err',url,e)

print('\n--- eastmoney abstract ---')
try:
    df=ak.stock_financial_abstract(symbol=symbol)
    print(df.shape); print(df.head(15).to_string())
    df.to_csv(out/'eastmoney_financial_abstract.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('ERR abstract',type(e).__name__,e)

print('\n--- eastmoney indicators ---')
try:
    df=ak.stock_financial_analysis_indicator(symbol=symbol)
    print(df.shape); print(df.head(15).to_string())
    df.to_csv(out/'eastmoney_financial_analysis_indicator.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('ERR indicator',type(e).__name__,e)

print('\n--- quote tencent/eastmoney if possible ---')
try:
    import requests
    for url in [f'https://qt.gtimg.cn/q=sz{symbol}', f'https://push2.eastmoney.com/api/qt/stock/get?secid=0.{symbol}&fields=f43,f57,f58,f84,f85,f116,f117,f127,f162,f167,f170,f173,f46,f60']:
        resp=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=15)
        print(url, resp.status_code, resp.text[:1000])
        (out/('quote_'+('tencent' if 'gtimg' in url else 'eastmoney')+'.txt')).write_text(resp.text,encoding='utf-8')
except Exception as e: print('quote err',e)
