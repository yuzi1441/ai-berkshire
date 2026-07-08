from pathlib import Path
raw=Path('grid_quotes_raw.tmp').read_text(encoding='gbk', errors='ignore')
rows=[]
for line in raw.splitlines():
    if '=' not in line or '"' not in line:
        continue
    code=line.split('=')[0].split('_')[-1]
    s=line.split('"',1)[1].rsplit('"',1)[0]
    f=s.split('~')
    name=f[1] if len(f)>1 else ''
    rows.append([name, f[2], f[3], f[32], f[45], f[39], f[46], f[47], f[48]])
print('name,code,price,chg_pct,mcap_yi,pe,pb,high52,low52')
for r in rows:
    print(','.join(r))
