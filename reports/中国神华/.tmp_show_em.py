import json, pathlib
j=json.loads(pathlib.Path('sources/live_data.json').read_text(encoding='utf-8'))
for key in ['em_annual','em_q1']:
 print('\n',key)
 data=j.get(key,{}).get('result',{}).get('data',[])
 for r in data[:6]:
  print(r.get('REPORT_DATE')[:10], r.get('REPORT_DATE_NAME'), 'revenue', r.get('TOTALOPERATEREVE'), 'net', r.get('PARENTNETPROFIT'), 'eps', r.get('EPSJB'), 'roe', r.get('ROEJQ'), 'bps', r.get('BPS'), 'rev_growth', r.get('TOTALOPERATEREVETZ'), 'profit_growth', r.get('PARENTNETPROFITTZ'))
