import json
from pathlib import Path
j=json.loads(Path('_tmp_eastmoney_raw.json').read_text(encoding='utf-8'))
# print keys recursively shallow
print(j.keys())
for k,v in j.items():
    print('TOP', k, type(v))
    if isinstance(v, dict):
        print(v.keys())
        for kk,vv in v.items():
            print(' ',kk,type(vv), (len(vv) if hasattr(vv,'__len__') else ''))
            if isinstance(vv, list):
                for item in vv[:5]:
                    print(item.keys())
                    print(item)
                    break
