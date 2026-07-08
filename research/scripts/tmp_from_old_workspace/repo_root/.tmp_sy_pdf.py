import pandas as pd, re, requests, os
os.makedirs('sources/002028', exist_ok=True)
# read all announcements and filter quarter reports
all_df=pd.read_csv('data/sy_cninfo_report_all_2024_2026.csv')
print(all_df[all_df['公告标题'].astype(str).str.contains('季度报告|一季度|第一季度|年度报告', regex=True, na=False)].head(40).to_string())
# test direct pdf urls
for aid,date,title in [('1225117829','2026-04-18','2025AR'),('1225117828','2026-04-18','2025AR_summary')]:
    url=f'http://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF'
    r=requests.get(url,timeout=20)
    print(title, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:20])
    open(f'sources/002028/{title}_{aid}.pdf','wb').write(r.content)
