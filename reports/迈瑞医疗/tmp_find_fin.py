from pathlib import Path
text=Path('source_pdfs/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['营业收入合计','基本每股收益','加权平均净资产收益率','经营活动产生的现金流量净额','每股企业自由现金流量','在建工程','购建固定资产','资本开支','现金及现金等价物余额','合并资产负债表','交易性金融资产']:
 print('\n###',term)
 idx=text.find(term)
 print(idx)
 if idx!=-1: print(text[max(0,idx-800):idx+1600])
