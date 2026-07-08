from pathlib import Path
text=Path('sources/联影医疗/2025年报.pdf.txt').read_text(encoding='utf-8')
patterns=['1. 分产品','分产品情况','按产品','主营业务分行业、分产品、分地区、分销售模式情况','主营业务分地区情况','境内','境外','磁共振','X 射线计算机断层扫描','分业务','医疗影像设备','医疗影像诊断','主要销售客户']
for pat in patterns:
    print('\n###',pat)
    start=0
    count=0
    while True:
        idx=text.find(pat,start)
        if idx<0: break
        print('@',idx, text[max(0,idx-500):idx+1800])
        start=idx+len(pat); count+=1
        if count>=3: break
