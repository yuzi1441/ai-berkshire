import akshare as ak, pandas as pd, json, os
symbol='000682'
code='SZ000682'
out='data/eastone_000682_raw'
os.makedirs(out, exist_ok=True)

def save(name, df):
    print('\n###',name, df.shape)
    print(df.head(10).to_string())
    print('columns:', list(df.columns))
    df.to_csv(os.path.join(out,name+'.csv'), index=False, encoding='utf-8-sig')

for name, func, args in [
 ('info_em', ak.stock_individual_info_em, dict(symbol=symbol)),
 ('spot_em_all', ak.stock_zh_a_spot_em, dict()),
 ('fin_ind_report', ak.stock_financial_analysis_indicator_em, dict(symbol='000682.SZ', indicator='按报告期')),
 ('fin_ind_quarter', ak.stock_financial_analysis_indicator_em, dict(symbol='000682.SZ', indicator='按单季度')),
 ('profit_report', ak.stock_profit_sheet_by_report_em, dict(symbol=code)),
 ('balance_report', ak.stock_balance_sheet_by_report_em, dict(symbol=code)),
 ('cash_report', ak.stock_cash_flow_sheet_by_report_em, dict(symbol=code)),
 ('zyjs_ths', ak.stock_zyjs_ths, dict(symbol=symbol)),
]:
    try:
        df=func(**args)
        if name=='spot_em_all': df=df[df['代码'].astype(str)==symbol]
        save(name, df)
    except Exception as e:
        print('ERR',name,repr(e))
# notices
for name, kw, cat in [('annual','年度报告','年报'),('q1','一季度报告','一季报')]:
    try:
        df=ak.stock_zh_a_disclosure_report_cninfo(symbol=symbol, keyword=kw, category=cat, start_date='20260101', end_date='20260707')
        save('notice_'+name, df)
    except Exception as e: print('ERR notice', name, repr(e))
