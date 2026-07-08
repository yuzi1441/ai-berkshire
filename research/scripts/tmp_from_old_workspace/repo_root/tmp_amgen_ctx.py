from pathlib import Path
text=Path('sources/beigene_management/2026_proxy.txt').read_text(encoding='utf-8')
for term in ['AMGEN INC.', 'Amgen Inc.', 'Security Ownership of Certain Beneficial Owners and Management', 'Based solely on information']:
    print(term, text.find(term))
# print all contexts around Amgen Inc occurrences in later portion
start=0
for i in range(10):
    idx=text.find('Amgen Inc', start)
    if idx==-1: break
    print('\nAMGEN occurrence', i, idx)
    print(text[max(0,idx-800):idx+1800])
    start=idx+1
