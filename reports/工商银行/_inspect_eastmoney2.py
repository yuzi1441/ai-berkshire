import json
from pathlib import Path
j=json.loads(Path('_tmp_eastmoney_raw.json').read_text(encoding='utf-8'))
for top in ['f10main','profit']:
    print('\nTOP',top)
    res=j[top]['result']
    print(res.keys())
    for k,v in res.items():
        print(' ',k,type(v),len(v) if hasattr(v,'__len__') else '')
        if isinstance(v,list) and v:
            print('  sample keys', v[0].keys())
            for item in v[:3]:
                print('  ', item)
