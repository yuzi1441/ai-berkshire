import pdfplumber, re, json
fn='sources/1225059012.PDF'
patterns=['生命信息与支持业务','体外诊断业务','医学影像业务','新兴业务','分行业','分产品','主营业务分','研发投入','销售费用','海外','高端客户','国内','境外','集采','集中带量','检验结果互认','渠道','转换成本','装机','产品注册证']
with pdfplumber.open(fn) as pdf:
    for i,p in enumerate(pdf.pages):
        text=p.extract_text() or ''
        hits=[pat for pat in patterns if pat in text]
        if hits:
            print(f'\n=== PAGE {i+1} hits={hits} ===')
            for line in text.split('\n'):
                if any(pat in line for pat in hits) or any(k in line for k in ['营业收入','毛利率','同比','研发','境外','集中带量','试剂','生命信息','体外诊断','医学影像','新兴业务','产品注册证','全球','客户','渠道','高端']):
                    print(line[:240])
