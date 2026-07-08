import akshare as ak
import pandas as pd
from pathlib import Path
out=Path('data_snapshots'); out.mkdir(exist_ok=True)
frames={
 'em_indicator': ak.stock_financial_analysis_indicator_em('000682.SZ'),
 'sina_indicator': ak.stock_financial_analysis_indicator('000682','2020'),
 'sina_abstract': ak.stock_financial_abstract('000682'),
 'em_profit': ak.stock_profit_sheet_by_report_em('SZ000682'),
 'em_balance': ak.stock_balance_sheet_by_report_em('SZ000682'),
 'em_cash': ak.stock_cash_flow_sheet_by_report_em('SZ000682'),
}
for name,df in frames.items():
    df.to_csv(out/f'{name}.csv', index=False, encoding='utf-8-sig')
    print(f'## {name} shape={df.shape}')
    print('columns=', list(df.columns))
    print(df.head(3).to_string(max_cols=30))
