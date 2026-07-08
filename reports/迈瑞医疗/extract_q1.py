import pdfplumber
fn='sources/1225229244.PDF'
with pdfplumber.open(fn) as pdf:
    for i,p in enumerate(pdf.pages):
        text=p.extract_text() or ''
        print(f'---PAGE {i+1}---')
        for line in text.split('\n'):
            if any(k in line for k in ['营业收入','归属于','净利润','研发','国内','国际','体外诊断','生命信息','医学影像','新兴业务','风险','下滑','增长']):
                print(line)
