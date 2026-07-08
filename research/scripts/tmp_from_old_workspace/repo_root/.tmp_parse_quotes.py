import re,json,os,requests,math
from pathlib import Path
from decimal import Decimal
# parse Tencent A/H quote raw saved by refetch
headers={'User-Agent':'Mozilla/5.0'}
quotes={}
for name,url in {'tencent_a':'https://qt.gtimg.cn/q=sh688235','sina_a':'https://hq.sinajs.cn/list=sh688235','tencent_hk':'https://qt.gtimg.cn/q=hk06160','yahoo_onc':'https://query1.finance.yahoo.com/v8/finance/chart/ONC?range=1d&interval=1m'}.items():
    try:
        r=requests.get(url,headers=headers,timeout=15)
        quotes[name]=r.text
    except Exception as e:
        quotes[name]=str(e)
os.makedirs('data',exist_ok=True)
Path('data/beigene_quotes_raw_20260706.txt').write_text('\n\n'.join(f'---{k}---\n{v}' for k,v in quotes.items()),encoding='utf-8')
# parse fields based on Tencent known format
# A fields from ~ separated: 3 current, 38 total mkt cap? 45 circ mkt? 46 PE? 51 PB? 72 total shares? 73 float shares? from string observed.
out={}
va=quotes['tencent_a'].split('="',1)[1].rsplit('"',1)[0].split('~')
out['A_Tencent']={'name':va[1],'code':va[2],'price_cny':float(va[3]),'prev_close':float(va[4]),'date_time':va[30], 'pe_ttm':va[39], 'pb':va[46], 'market_cap_yi_cny_field45_or46':va[45:47], 'total_shares_field72':va[72] if len(va)>72 else None, 'raw_len':len(va)}
# Sina A: name, open, prev close, current etc
sa=quotes['sina_a'].split('="',1)[1].rsplit('"',1)[0].split(',')
out['A_Sina']={'name':sa[0],'price_cny':float(sa[3]),'prev_close':float(sa[2]),'date':sa[30],'time':sa[31]}
# HK
vh=quotes['tencent_hk'].split('="',1)[1].rsplit('"',1)[0].split('~')
out['HK_Tencent']={'name':vh[1],'code':vh[2],'price_hkd':float(vh[3]),'prev_close':float(vh[4]),'date_time':vh[30], 'market_cap_hkd_bn_maybe':vh[45], 'shares_total':vh[68] if len(vh)>68 else None,'raw_len':len(vh)}
# Yahoo ONC
try:
 j=json.loads(quotes['yahoo_onc'])['chart']['result'][0]
 meta=j['meta']
 out['US_Yahoo']={'symbol':meta['symbol'],'price_usd':meta['regularMarketPrice'],'prev_close':meta['previousClose'],'time':meta['regularMarketTime'],'currency':meta['currency'],'longName':meta.get('longName'),'fiftyTwoWeekHigh':meta.get('fiftyTwoWeekHigh'),'fiftyTwoWeekLow':meta.get('fiftyTwoWeekLow')}
except Exception as e: out['US_Yahoo_parse_error']=str(e)
# company basics
shares_ord=1442451870 # Q1 diluted? actual weighted basic q1. use outstanding 2026? for ADS equiv divide 13
shares_10k=1442259810
ads_equiv=shares_10k/13
out['share_assumptions']={'ordinary_shares_10k_2026_02_13':shares_10k,'ADS_equiv':ads_equiv,'ADS_ratio':'1 ADS = 13 ordinary shares'}
# calculations
price_us=Decimal(str(out['US_Yahoo']['price_usd']))
mc_us=price_us*Decimal(str(ads_equiv))
out['market_cap_calc_usd']={'price_usd_per_ads':str(price_us),'ads_equiv':str(Decimal(str(ads_equiv))), 'market_cap_usd':str(mc_us), 'market_cap_usd_billion':str(mc_us/Decimal('1e9'))}
price_a=Decimal(str(out['A_Tencent']['price_cny']))
mc_a=price_a*Decimal(shares_10k)
out['market_cap_calc_a_cny']={'price_cny_per_share':str(price_a),'ordinary_shares':str(shares_10k),'market_cap_cny':str(mc_a),'market_cap_cny_billion':str(mc_a/Decimal('1e9'))}
price_h=Decimal(str(out['HK_Tencent']['price_hkd']))
mc_h=price_h*Decimal(shares_10k)
out['market_cap_calc_h_hkd']={'price_hkd_per_share':str(price_h),'ordinary_shares':str(shares_10k),'market_cap_hkd':str(mc_h),'market_cap_hkd_billion':str(mc_h/Decimal('1e9'))}
Path('data/beigene_quote_parsed_20260706.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))