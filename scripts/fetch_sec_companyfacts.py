import json
import time
import urllib.request
from pathlib import Path

BASE = Path('data/sec_companyfacts_20260706')
BASE.mkdir(exist_ok=True)
WANT = {
    'ETN': '0001551182',
    'VRT': '0001674101',
    'GEV': '0001996810',
    'POWL': '0000080420',
    'NVT': '0001720635',
    'HUBB': '0000048898',
    'PWR': '0001050915',
    'CEG': '0001868275',
    'VST': '0001692819',
    'TLN': '0001622536',
}
for sym, cik in WANT.items():
    url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
    out = BASE / f'{sym}_{cik}.json'
    if out.exists() and out.stat().st_size > 10000:
        print(sym, 'exists', out.stat().st_size)
        continue
    req = urllib.request.Request(url, headers={'User-Agent': 'ai-berkshire research contact@example.com'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        out.write_bytes(data)
        print(sym, len(data))
        time.sleep(0.2)
    except Exception as e:
        print(sym, 'ERR', e)
