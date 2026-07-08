import akshare as ak
for cat in ['年报','一季报','半年报','三季报','权益分派','日常经营','公司治理']:
 print('\n==',cat,'==')
 try:
  df=ak.stock_zh_a_disclosure_report_cninfo(symbol='600312', market='沪深京', category=cat, start_date='20250101', end_date='20260707')
  print(df.shape)
  print(df.head(10).to_string())
  print(df.columns.tolist())
 except Exception as e: print('ERR',repr(e))
