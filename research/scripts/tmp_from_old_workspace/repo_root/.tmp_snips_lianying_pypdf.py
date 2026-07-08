from pathlib import Path
text=Path('sources/联影医疗/lianying_annual_20260429_1225233728.pdf.pypdf.txt').read_text(encoding='utf-8', errors='ignore')
# print as unicode-escaped for exact matching? no, write snippets to file normally.
patterns=['主要会计数据','营业收入','分行业','分产品','分地区','医学影像诊断设备','收入构成','境外','研发投入','市场占有率','专利申请','前五名客户','前五名供应商','毛利率','风险因素','股东总数','实际控制人','张强','薛敏','经营活动产生的现金流量净额','货币资金','存货','合同负债']
out=[]
for pat in patterns:
    out.append('\n===== PAT '+pat+' =====')
    start=0; count=0
    while True:
        idx=text.find(pat,start)
        if idx<0 or count>=3: break
        out.append('--- idx '+str(idx)+' ---')
        out.append(text[max(0,idx-700):idx+1800])
        start=idx+len(pat); count+=1
Path('data/lianying_snips_pypdf_utf8.txt').write_text('\n'.join(out),encoding='utf-8')
print('wrote', Path('data/lianying_snips_pypdf_utf8.txt').stat().st_size)
