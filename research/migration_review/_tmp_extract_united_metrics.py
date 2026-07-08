import pathlib,re,json,akshare as ak,pandas as pd
root=pathlib.Path('reports/联影医疗')
src=root/'sources'
# save ak financial abstract as csv/json
fin=ak.stock_financial_abstract(symbol='688271')
fin.to_csv(src/'ak_financial_abstract.csv',index=False,encoding='utf-8-sig')
ths=ak.stock_financial_abstract_ths(symbol='688271')
ths.to_csv(src/'ak_financial_abstract_ths.csv',index=False,encoding='utf-8-sig')
# Pull selected metrics from fin by indicator rows
cols=['20260331','20251231','20241231','20231231','20221231','20211231','20201231','20191231','20181231']
indicators=['营业总收入','归母净利润','扣非净利润','经营现金流量净额','基本每股收益','每股净资产','净资产收益率(ROE)','毛利率','销售净利率','资产负债率','股东权益合计(净资产)']
sel=fin[fin['指标'].isin(indicators)][['指标']+cols]
print(sel.to_string(index=False))
sel.to_csv(src/'selected_metrics.csv',index=False,encoding='utf-8-sig')
# snippets from annual
for fname in ['2025Annual.txt','2026Q1.txt','2024Annual.txt']:
 text=(src/fname).read_text(encoding='utf-8',errors='ignore')
 print('\n====',fname,'====')
 for pat in ['主要会计数据和财务指标','近三年主要会计数据和财务指标','营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','分季度主要财务数据','研发投入','现金分红','市场占有率','市场份额','国产','产品线','回购','限制性股票','总资产','货币资金','存货','应收账款','长期借款','短期借款','公司所从事的主要业务','行业情况']:
  m=re.search(pat,text)
  if m:
   s=max(0,m.start()-500); e=min(len(text),m.start()+1800)
   print('\n--',pat,'--')
   print(text[s:e].replace('\n',' ')[:2200])
