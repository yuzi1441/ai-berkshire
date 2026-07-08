from pathlib import Path
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
for term in ['经营活动产生的现金流量净额','研发投入金额','研发投入','公司研发人员情况','董事长','李西廷','公司前5大客户资料','公司前5名供应商资料','货币资金','主要控股参股公司分析','国际市场','国内市场','医疗新基建','设备更新','集采','反腐','商誉','行业竞争']:
    print('\n###',term)
    start=0; count=0
    while True:
        idx=text.find(term,start)
        if idx<0: break
        print('idx',idx)
        print(text[max(0,idx-600):idx+1600])
        count+=1; start=idx+len(term)
        if count>=3: break
