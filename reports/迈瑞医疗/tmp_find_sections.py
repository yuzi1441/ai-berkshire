from pathlib import Path
text=Path('source_pdfs/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
terms=['营业收入构成','分行业','生命信息与支持','体外诊断','医学影像','微创外科','全球','国内','市场份额','利润分配','李西廷','徐航','成明和','医疗器械','风险','资本开支','研发投入','现金及现金等价物','货币资金','商誉','分产品']
for term in terms:
    print('\n### TERM',term)
    idx=text.find(term)
    print('idx',idx)
    if idx!=-1:
        print(text[max(0,idx-800):idx+1800])
