import pandas as pd
from pathlib import Path
ind=pd.read_csv(Path('..')/'..'/'data'/'hudian_indicator_sina.csv')
cols=['日期','摊薄每股收益(元)','每股净资产_调整前(元)','每股经营性现金流(元)','销售净利率(%)','销售毛利率(%)','净资产收益率(%)','加权净资产收益率(%)','资产负债率(%)','流动比率','速动比率','经营现金净流量与净利润的比率(%)','主营业务收入增长率(%)','净利润增长率(%)','总资产(元)']
print(ind[cols].tail(12).to_string(index=False))
