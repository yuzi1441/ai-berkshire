from pathlib import Path
text=Path('sources/联影医疗/lianying_q1_20260429_1225233744.pdf.pypdf.txt').read_text(encoding='utf-8')
for pat in ['货币资金','交易性金融资产','短期借款','长期借款','合同负债','应收账款','存货']:
 idx=text.find(pat)
 print('\n',pat, idx)
 print(text[max(0,idx-400):idx+1000] if idx>=0 else '')
