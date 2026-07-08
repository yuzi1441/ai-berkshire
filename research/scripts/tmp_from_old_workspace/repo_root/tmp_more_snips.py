import re
from pathlib import Path
for fname in ['2025_10k.txt','2026_q1_10q.txt','2025_results_pr.txt','2026_q1_pr.txt','2026_proxy.txt']:
    text=Path('sources/beigene_management/'+fname).read_text(encoding='utf-8')
    for pat in ['In 2025, we achieved','full year 2026 total revenue guidance','Total global revenues of','Free Cash Flow','capital expenditures','related person transactions','Certain Relationships and Related-Party Transactions','clawback','recoupment']:
        idx=text.lower().find(pat.lower())
        if idx!=-1:
            print('\nFILE',fname,'PAT',pat,'IDX',idx)
            print(text[max(0,idx-350):idx+1200].replace('\n',' '))
