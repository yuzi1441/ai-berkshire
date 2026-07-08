import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 50)
for name, func, kwargs in [
    ('individual', ak.stock_individual_info_em, {'symbol':'600312'}),
    ('spot', ak.stock_zh_a_spot_em, {}),
    ('abstract', ak.stock_financial_abstract, {'symbol':'600312'}),
    ('indicator', ak.stock_financial_analysis_indicator, {'symbol':'600312'}),
    ('indicator_em', ak.stock_financial_analysis_indicator_em, {'symbol':'600312'}),
]:
    print('---', name, '---')
    try:
        df=func(**kwargs)
        if name=='spot':
            df=df[df['代码'].astype(str)=='600312']
        print(df.head(10).to_string())
        print(df.columns.tolist())
    except Exception as e:
        print(type(e).__name__, e)
