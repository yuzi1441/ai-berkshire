from pathlib import Path
import pandas as pd, json, re, urllib.request
root=Path.cwd()
# Load known CSVs
ind=pd.read_csv(root/'..'/'..'/'data'/'hudian_indicator_sina.csv')
latest=ind.iloc[-1]
annual=ind[ind['日期'].str.endswith('12-31')].tail(6)
# Tencent quote parsed from saved live fetch string embedded manually? Refetch for reproducible snapshot.
url='https://qt.gtimg.cn/q=sz002463'
req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'})
text=urllib.request.urlopen(req, timeout=15).read().decode('gbk','ignore')
raw=text.split('="',1)[1].rsplit('"',1)[0].split('~')
quote={
 'name': raw[1], 'code': raw[2], 'price': float(raw[3]), 'prev_close': float(raw[4]), 'open': float(raw[5]),
 'volume_lot': raw[6], 'datetime': raw[30], 'change': float(raw[31]), 'pct': float(raw[32]), 'high': float(raw[33]), 'low': float(raw[34]),
 'turnover_rate': float(raw[38]), 'pe_ttm_tencent': float(raw[39]), 'market_cap_billion': float(raw[45]), 'float_cap_billion': float(raw[44]),
 'pb_tencent': float(raw[46]), 'shares_float': int(raw[72]), 'shares_total': int(raw[73]),
 'source': '腾讯行情 qt.gtimg.cn 2026-07-06 16:14:54'
}
# Sina quote refetch
sina=urllib.request.urlopen(urllib.request.Request('https://hq.sinajs.cn/list=sz002463',headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}), timeout=15).read().decode('gbk','ignore')
svals=sina.split('="',1)[1].rsplit('"',1)[0].split(',')
sina_quote={'price':float(svals[3]), 'prev_close':float(svals[2]), 'open':float(svals[1]), 'high':float(svals[4]), 'low':float(svals[5]), 'volume_shares':int(svals[8]), 'amount':float(svals[9]), 'date':svals[30], 'time':svals[31], 'source':'新浪行情 hq.sinajs.cn'}
# Core values from filings
core={
 'annual_2025': {'revenue':18945220585,'net_profit_parent':3822306272,'deducted_net_profit':3760567906,'ocf':3871967792,'eps_basic':1.9875,'roe_weighted_pct':28.57,'total_assets':28254274039,'equity_parent':15112704642,'gross_margin_pcb_pct':36.91,'data_comm_revenue':14656300288,'smart_auto_revenue':3044579100,'customer_top5_sales':10102760452,'customer_top5_pct':53.32,'rd_expense':1140945544,'dividend_per_share':0.5,'cash_dividend':962181768.5,'cash':2579107305,'receivables':5507160245,'inventory':4245940570,'short_debt':2169945664,'long_debt':1885660527,'liabilities':13126187360,'capex_building':2700000000},
 'q1_2026': {'revenue':6214156406,'net_profit_parent':1242081367,'deducted_net_profit':1162681935,'ocf':511016585,'eps_basic':0.6455,'roe_weighted_pct':7.81,'total_assets':32720019199,'equity_parent':16789869984}
}
# Derived
price=quote['price']; shares=quote['shares_total']; eps_ttm=1.9844+0.6451-0.3953 # indicator diluted-ish trailing EPS; report basic eps 2025+q1 delta approx 2.2377? use net profits maybe
np_ttm=3822306272+1242081367-762465400
eps_ttm_np=np_ttm/shares
bvps=core['q1_2026']['equity_parent']/shares
fcf_2025=(core['annual_2025']['ocf']-core['annual_2025']['capex_building'])/shares
metrics={
 'price':price,'shares':shares,'market_cap':price*shares,'eps_ttm_from_profit':eps_ttm_np,'bvps_q1':bvps,'pe_ttm_calc':price/eps_ttm_np,'pb_calc':price/bvps,'dividend_yield':core['annual_2025']['dividend_per_share']/price,'fcf_per_share_rough':fcf_2025,'fcf_yield_rough':fcf_2025/price,'net_debt_2025':core['annual_2025']['short_debt']+core['annual_2025']['long_debt']-core['annual_2025']['cash']}
# Write JSON evidence
out={'quote_tencent':quote,'quote_sina':sina_quote,'core':core,'metrics':metrics,'annual_indicator_tail':annual[['日期','摊薄每股收益(元)','每股净资产_调整前(元)','每股经营性现金流(元)','销售净利率(%)','净资产收益率(%)','加权净资产收益率(%)','资产负债率(%)','主营业务收入增长率(%)','净利润增长率(%)']].to_dict('records')}
(root/'hudian_checklist_data.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
