import pdfplumber, re, pathlib
files=['icbc_2025_annual_A.pdf','icbc_2026_q1_A.pdf']
terms=['利息净收入','手续费及佣金净收入','营业收入','净利息差','公司金融业务','个人金融业务','金融市场业务','金融科技','网络金融','个人客户','公司客户','客户存款','客户贷款','境内分行','手机银行','普惠金融','结算','银行卡','资产管理','绿色金融','科技金融']
for fn in files:
    print('\n====',fn,'====')
    with pdfplumber.open(fn) as pdf:
        for term in terms:
            hits=[]
            for i,p in enumerate(pdf.pages):
                text=p.extract_text() or ''
                if term in text:
                    hits.append(i+1)
            if hits:
                print(term, hits[:10], 'count', len(hits))
