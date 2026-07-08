import akshare as ak
import pandas as pd
from pathlib import Path
symbols={
 '四方股份':'SH601126',
 '国电南瑞':'SH600406',
 '许继电气':'SZ000400',
 '平高电气':'SH600312',
 '思源电气':'SZ002028',
}
rows=[]
for name,sym in symbols.items():
    p=ak.stock_profit_sheet_by_report_em(sym)
    c=ak.stock_cash_flow_sheet_by_report_em(sym)
    for date,period in [('2026-03-31 00:00:00','2026Q1'),('2025-12-31 00:00:00','2025A')]:
        pr=p[p['REPORT_DATE'].astype(str)==date]
        cf=c[c['REPORT_DATE'].astype(str)==date]
        if pr.empty:
            print('missing profit', name, period)
            continue
        pr=pr.iloc[0]
        cf=cf.iloc[0] if not cf.empty else pd.Series(dtype='object')
        row={
          '公司':name,'代码':sym,'期间':period,'公告日':pr.get('NOTICE_DATE'),
          '营业收入_亿元':pr.get('TOTAL_OPERATE_INCOME')/1e8 if pd.notna(pr.get('TOTAL_OPERATE_INCOME')) else None,
          '收入同比_%':pr.get('TOTAL_OPERATE_INCOME_YOY'),
          '营业成本_亿元':pr.get('OPERATE_COST')/1e8 if pd.notna(pr.get('OPERATE_COST')) else None,
          '归母净利润_亿元':pr.get('PARENT_NETPROFIT')/1e8 if pd.notna(pr.get('PARENT_NETPROFIT')) else None,
          '归母净利同比_%':pr.get('PARENT_NETPROFIT_YOY'),
          '扣非归母_亿元':pr.get('DEDUCT_PARENT_NETPROFIT')/1e8 if pd.notna(pr.get('DEDUCT_PARENT_NETPROFIT')) else None,
          '扣非同比_%':pr.get('DEDUCT_PARENT_NETPROFIT_YOY'),
          '研发费用_亿元':pr.get('RESEARCH_EXPENSE')/1e8 if pd.notna(pr.get('RESEARCH_EXPENSE')) else None,
          '销售费用_亿元':pr.get('SALE_EXPENSE')/1e8 if pd.notna(pr.get('SALE_EXPENSE')) else None,
          '管理费用_亿元':pr.get('MANAGE_EXPENSE')/1e8 if pd.notna(pr.get('MANAGE_EXPENSE')) else None,
          '经营现金流_亿元':cf.get('NETCASH_OPERATE')/1e8 if 'NETCASH_OPERATE' in cf and pd.notna(cf.get('NETCASH_OPERATE')) else None,
          '毛利率_%':((pr.get('TOTAL_OPERATE_INCOME')-pr.get('OPERATE_COST'))/pr.get('TOTAL_OPERATE_INCOME')*100) if pd.notna(pr.get('TOTAL_OPERATE_INCOME')) and pd.notna(pr.get('OPERATE_COST')) else None,
          '净利率_%':(pr.get('PARENT_NETPROFIT')/pr.get('TOTAL_OPERATE_INCOME')*100) if pd.notna(pr.get('TOTAL_OPERATE_INCOME')) and pd.notna(pr.get('PARENT_NETPROFIT')) else None,
          '研发费率_%':(pr.get('RESEARCH_EXPENSE')/pr.get('TOTAL_OPERATE_INCOME')*100) if pd.notna(pr.get('TOTAL_OPERATE_INCOME')) and pd.notna(pr.get('RESEARCH_EXPENSE')) else None,
        }
        rows.append(row)

df=pd.DataFrame(rows)
for col in df.select_dtypes(include='number').columns:
    df[col]=df[col].round(2)
Path('peer_financials_akshare.csv').write_text(df.to_csv(index=False),encoding='utf-8-sig')
print(df.to_string(index=False))
