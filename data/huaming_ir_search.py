import pandas as pd
p='data/huaming_002270/cninfo_report_all_2024_2026.csv'
df=pd.read_csv(p)
mask=df['公告标题'].astype(str).str.contains('投资者关系|调研|业绩说明|说明会|接待|活动记录|电话会|交流', na=False, regex=True)
print(df[mask][['公告标题','公告时间','公告链接']].head(50).to_string(index=False))
