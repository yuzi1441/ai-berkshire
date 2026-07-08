from pathlib import Path
text=Path('_icbc_finreports.html').read_text(encoding='utf-8')
for needle in ['2025 Annual Report','Annual Report','First Quarterly','Quarterly Report','2026']:
 print('\nNEEDLE',needle)
 idx=0
 while True:
  i=text.lower().find(needle.lower(),idx)
  if i<0: break
  print('pos',i, text[max(0,i-300):i+500].replace('\n',' ')[:1000])
  idx=i+1