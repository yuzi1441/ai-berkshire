import pdfplumber, re
for pdf in ['icbc_2025_annual_A.pdf','icbc_2026_q1_A.pdf']:
    print('\nPDF',pdf)
    with pdfplumber.open(pdf) as doc:
        text='\n'.join((p.extract_text() or '') for p in doc.pages)
    terms=['每股收益','归属于母公司股东的权益','归属于母公司普通股股东的每股净资产','普通股每股现金股息','加权平均权益回报率','资产总额','归属于母公司股东的净利润','经营活动产生的现金流量净额']
    for term in terms:
        idx=text.find(term)
        print('\nTERM',term,'idx',idx)
        if idx!=-1:
            print(text[max(0,idx-300):idx+600].replace('\n',' '))