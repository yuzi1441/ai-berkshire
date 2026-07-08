import pdfplumber, pathlib, re, json
base=pathlib.Path('sources/oriental_electronics')
for pdf in base.glob('*.pdf'):
 print('\nPDF',pdf.name)
 with pdfplumber.open(pdf) as p:
  print('pages',len(p.pages))
  text='\n'.join((page.extract_text() or '') for page in p.pages)
  (base/(pdf.stem+'.txt')).write_text(text,encoding='utf-8')
  for kw in ['主营业务','业务概述','主要业务','智能电网','营业收入构成','分行业','分产品','毛利率','研发投入','前五名客户','前五名供应商','应收账款','存货','分红','股东信息','实际控制人','董事长','权益分派']:
   i=text.find(kw)
   if i!=-1:
    sn=text[max(0,i-160):i+500].replace('\n',' ')
    print('KW',kw, sn[:650])
