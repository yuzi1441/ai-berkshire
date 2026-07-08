import json
from pathlib import Path

data=json.loads(Path('data/hengrui_mainfina_all.json').read_text(encoding='utf-8'))
rows=data['result']['data']
raw=Path('data/hengrui_quote_raw.txt').read_text(encoding='utf-8')
fields=raw[raw.find('"')+1:raw.rfind('"')].split('~')
for i,v in enumerate(fields):
    if i<90: print(i, v)
