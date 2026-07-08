from pathlib import Path
text=Path('sources/beigene_management/2026_proxy.txt').read_text(encoding='utf-8')
terms=['Executive Officers','Name Age Position','Summary Compensation Table','Security Ownership of Certain Beneficial Owners','Pay Versus Performance','2025 Summary Compensation Table','Director Compensation','Related Person Transactions','Compensation Discussion and Analysis','no controlling shareholder','controlled company','John V. Oyler','Aaron Rosenberg','Xiaobin Wu']
for term in terms:
    print('\n===',term,'===')
    idx=text.lower().find(term.lower())
    print('idx',idx)
    if idx!=-1:
        print(text[max(0,idx-1200):idx+3000])
