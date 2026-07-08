from pathlib import Path
text=Path('sources/四方股份/hkex_application_20260616.txt').read_text(encoding='utf-8').splitlines()
keywords=['五大客戶','五大供應商','客戶','生產質量','重大處罰','質量','產品交付','保修','行業地位','市場份額','國家電網','南方電網','海外']
for kw in keywords:
 print('\n--',kw)
 for i,l in [(i+1,l.strip()) for i,l in enumerate(text) if kw in l][:12]:
  print(f'{i}: {l[:240]}')
