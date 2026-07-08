import re,json,os
from pathlib import Path
from decimal import Decimal
raw=Path('data/beigene_quotes_raw_20260706.txt').read_text(encoding='utf-8')
sections={}
for part in raw.split('\n\n---'):
    part=part.strip()
    if not part: continue
    if part.startswith('---'): part=part[3:]
    name,_,body=part.partition('---\n')
    sections[name.strip('-')]=body.strip()
out={}
va=sections['tencent_a'].split('="',1)[1].rsplit('"',1)[0].split('~')
out['A_Tencent']={'name':va[1],'code':va[2],'price_cny':float(va[3]),'prev_close':float(va[4]),'date_time':va[30], 'pe_ttm':float(va[39]), 'pb':float(va[46]), 'market_cap_yi_cny':float(va[45]), 'total_shares_raw':float(va[72]), 'float_a_shares_raw':float(va[73]), 'raw_len':len(va)}
try:
    sa=sections['sina_a'].split('="',1)[1].rsplit('"',1)[0].split(',')
    out['A_Sina']={'name':sa[0],'price_cny':float(sa[3]),'prev_close':float(sa[2]),'date':sa[30],'time':sa[31]}
except Exception as e:
    out['A_Sina_error']=sections.get('sina_a','')[:50] or str(e)
vh=sections['tencent_hk'].split('="',1)[1].rsplit('"',1)[0].split('~')
out['HK_Tencent']={'name':vh[1],'code':vh[2],'price_hkd':float(vh[3]),'prev_close':float(vh[4]),'date_time':vh[30], 'market_cap_hkd_bn':float(vh[45]), 'shares_total_raw':float(vh[68]),'raw_len':len(vh)}
j=json.loads(sections['yahoo_onc'])['chart']['result'][0]
meta=j['meta']
out['US_Yahoo']={'symbol':meta['symbol'],'price_usd':meta['regularMarketPrice'],'prev_close':meta['previousClose'],'time':meta['regularMarketTime'],'currency':meta['currency'],'longName':meta.get('longName'),'fiftyTwoWeekHigh':meta.get('fiftyTwoWeekHigh'),'fiftyTwoWeekLow':meta.get('fiftyTwoWeekLow')}
shares_10k=1442259810
ads_equiv=Decimal(shares_10k)/Decimal(13)
out['share_assumptions']={'ordinary_shares_10k_2026_02_13':shares_10k,'ADS_equiv':float(ads_equiv),'ADS_ratio':'1 ADS = 13 ordinary shares'}
price_us=Decimal(str(out['US_Yahoo']['price_usd']))
mc_us=price_us*ads_equiv
out['market_cap_calc_usd']={'price_usd_per_ads':str(price_us),'ads_equiv':str(ads_equiv), 'market_cap_usd':str(mc_us), 'market_cap_usd_billion':str(mc_us/Decimal('1e9'))}
price_a=Decimal(str(out['A_Tencent']['price_cny']))
mc_a=price_a*Decimal(shares_10k)
out['market_cap_calc_a_cny']={'price_cny_per_share':str(price_a),'ordinary_shares':str(shares_10k),'market_cap_cny':str(mc_a),'market_cap_cny_billion':str(mc_a/Decimal('1e9'))}
price_h=Decimal(str(out['HK_Tencent']['price_hkd']))
mc_h=price_h*Decimal(shares_10k)
out['market_cap_calc_h_hkd']={'price_hkd_per_share':str(price_h),'ordinary_shares':str(shares_10k),'market_cap_hkd':str(mc_h),'market_cap_hkd_billion':str(mc_h/Decimal('1e9'))}
Path('data/beigene_quote_parsed_20260706.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))