import json

with open(r'data\investment-dashboard\decision_board.json', encoding='utf-8') as f:
    data = json.load(f)

ashare = [d for d in data['decisions'] if d.get('market') == 'A股']
print('A股 companies:', len(ashare))
total_reports = 0
for d in ashare:
    total_reports += len(d.get('report_history') or [])
print('total history reports:', total_reports)
print()
for d in ashare:
    hist = d.get('report_history') or []
    hist_paths = ';'.join(h.get('title', '')[:40] + '@' + (h.get('action') or '?') for h in hist[:1])
    print('|'.join([
        d.get('company', ''),
        d.get('ticker', '') or '',
        d.get('action', '') or '未提取',
        (d.get('data_cutoff', '') or '无')[:10],
        d.get('buy_price', '') or '-',
        (d.get('conclusion_summary', '') or '')[:60].replace('|', '/'),
        d.get('report_path', ''),
    ]))
