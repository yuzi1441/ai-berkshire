from pathlib import Path
text=Path('sources/联影医疗/lianying_annual_20260429_1225233728.pdf.pypdf.txt').read_text(encoding='utf-8')
for pat in ['研发人员数量','研发投入合计','研发投入资本化','公司研发人员','研发投入总额','研发人员情况表','累计专利','专利申请量','专利申请']:
    print('\nPAT',pat)
    start=0; c=0
    while True:
        idx=text.find(pat,start)
        if idx<0 or c>=5: break
        print('idx',idx)
        print(text[max(0,idx-500):idx+1200])
        start=idx+len(pat); c+=1
