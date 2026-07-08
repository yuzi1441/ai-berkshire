import pdfplumber, pathlib, re
for b in ['BOCOM','PSBC','CMB']:
 path=pathlib.Path('source_pdfs')/f'{b}_Q1_2026.pdf'
 print('\n###',b)
 with pdfplumber.open(path) as pdf:
  for i,p in enumerate(pdf.pages):
   text=p.extract_text() or ''
   if any(k in text for k in ['经营业绩','营业收入','净利息收益率','净利润','不良贷款率','客户贷款','发放贷款','资本充足率']):
    print('\n--page',i+1)
    for line in text.split('\n'):
     if any(k in line for k in ['营业收入','利息净收入','归属于母公司','归属于银行股东的净利润','归属于本行股东的净利润','净利息收益率','不良贷款率','拨备覆盖率','客户贷款','发放贷款','资本充足率','核心一级']):
      print(line)
