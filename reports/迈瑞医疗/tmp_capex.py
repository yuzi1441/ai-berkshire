from pathlib import Path
text=Path('source_pdfs/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['购建固定资产、无形资产和其他长期资产支付的现金','固定资产、无形资产和其他长期资产','资本性支出','取得子公司及其他营业单位支付的现金净额','支付其他与投资活动有关的现金']:
 print('\n###',term)
 idx=text.find(term)
 print(idx)
 if idx!=-1: print(text[max(0,idx-1000):idx+1600])
