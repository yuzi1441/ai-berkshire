from pathlib import Path
for fname in ['2025_results_8k.txt','2026_q1_8k.txt','2026_june_8k.txt','2026_june26_8k.txt']:
 text=Path('sources/beigene_management/'+fname).read_text(encoding='utf-8')
 print('\n====',fname,'====')
 for term in ['John V. Oyler','Aaron Rosenberg','Total revenue','BRUKINSA','profit','profitable','guidance','2026 Financial Guidance','Operating income','change its global name','redomiciliation','Annual General Meeting','director','elected']:
  idx=text.lower().find(term.lower())
  print('\n--',term,idx,'--')
  if idx!=-1: print(text[max(0,idx-500):idx+2500].replace('\n',' ')[:3000])
