import pdfplumber
with pdfplumber.open('icbc_2026_q1_cn_A.pdf') as p:
 print('pages',len(p.pages))
 for i in range(1,12):
  txt=p.pages[i-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
  if any(k in txt for k in ['营业收入','营业总收入','利息收入','归属于母公司股东','加权平均净资产收益率','不良贷款率','资本充足率']):
   print('\n---PAGE',i,'---')
   print(txt[:3000])