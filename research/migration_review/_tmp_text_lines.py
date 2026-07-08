from bs4 import BeautifulSoup
for file in ['reports/工商银行/_tmp_1228714343244328961.html.html','reports/工商银行/_tmp_1210891474012143617.html.html']:
 print('\n',file)
 soup=BeautifulSoup(open(file,encoding='utf-8').read(),'html.parser')
 text=soup.get_text('\n',strip=True)
 lines=[l for l in text.split('\n') if l.strip()]
 for i,l in enumerate(lines):
  if any(k in l for k in ['2025年年度报告','2025 年度','2025年度','中国工商银行股份有限公司2025','第一季度','年度报告','季报','财务报告']):
   print(i, l[:200])
   print(' next', lines[i+1:i+5])