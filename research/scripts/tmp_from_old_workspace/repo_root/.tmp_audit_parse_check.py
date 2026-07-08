from pathlib import Path
p=Path('sources/长江电力/audit_extract_seed42.txt')
t=p.read_text(encoding='utf-8')
start=t.find('[\n')
print('start',start,'len',len(t))
print(t[start:start+500])
