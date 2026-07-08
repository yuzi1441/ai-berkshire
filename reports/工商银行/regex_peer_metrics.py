import pdfplumber, pathlib, re, json
banks={'ICBC':'工商','CCB':'建行','ABC':'农行','BOC':'中行','BOCOM':'交行','PSBC':'邮储','CMB':'招行'}
patterns={
'rev':r'营业收入\s+([\d,]+)\s+(?:[\d,]+\s+)?([\d.]+)',
'np':r'(?:归属于(?:母公司|本行|银行).*?净利润|净利润（归属于母公司股东）)\s+([\d,]+)\s+(?:[\d,]+\s+)?([\d.]+)',
}
for b,cn in banks.items():
 path=pathlib.Path('source_pdfs')/f'{b}_Q1_2026.pdf'
 with pdfplumber.open(path) as pdf:
  text='\n'.join((p.extract_text() or '') for p in pdf.pages)
 print('\n',b,cn)
 for name,pat in patterns.items():
  m=re.search(pat,text)
  print(name, m.groups() if m else None)
 # manual other values from snippets via regex
 for label,pat in [('nii',r'利息净收入\s*([\d,.]+)\s*亿元[^\n。；]*?(?:增长|同比增长)([\d.]+)%'),('nim',r'(?:净利息收益率|净息差)(?:为)?\s*([\d.]+)%'),('npl',r'不良贷款率\s*([\d.]+)%'),('cov',r'拨备覆盖率\s*([\d.]+)%'),('loan',r'(?:客户贷款及垫款总额（不含应计利息）|发放贷款和垫款总额|客户贷款余额|客户贷款总额|贷款和垫款总额)(?:[^\d]{0,20})([\d,.]+)\s*(?:亿元|万亿元)')]:
  m=re.search(pat,text)
  print(label,m.group(1,2) if (m and label=='nii') else (m.group(1) if m else None))
