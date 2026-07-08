from pathlib import Path
text=Path('source_pdfs/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
idx=text.find('购买商品、接受劳务支付的现金')
print(idx)
print(text[max(0,idx-2000):idx+3000])
