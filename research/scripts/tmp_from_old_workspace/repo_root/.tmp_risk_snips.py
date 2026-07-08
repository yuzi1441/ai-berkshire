from pathlib import Path
text=Path('sources/长江电力/cypc_2025_annual.pdf.txt').read_text(encoding='utf-8')
for pat in ['长江来水风险','电力市场化风险','利率风险','安全生产风险','大坝安全','生态环保','汇率风险']:
 print('\n###',pat)
 i=text.find(pat)
 print(i, text[i-200:i+900].replace('\n',' | ') if i>=0 else '')
