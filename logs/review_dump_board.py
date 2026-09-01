import json

with open(r'data\investment-dashboard\decision_board.json', encoding='utf-8') as f:
    data = json.load(f)

rows = []
for d in data['decisions']:
    rows.append('|'.join([
        d.get('company', ''),
        d.get('ticker', '') or '',
        d.get('market', '') or '',
        d.get('action', '') or '',
        (d.get('data_cutoff', '') or '')[:10],
        str(d.get('report_history_count', '')),
        (d.get('report_path', '') or '').replace('\\', '/'),
    ]))
print('\n'.join(rows))
