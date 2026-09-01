import json

with open(r'data\investment-dashboard\decision_board.json', encoding='utf-8') as f:
    data = json.load(f)

for d in data['decisions']:
    if d['company'] in ('五粮液', '深南电路', '生益科技', '湖南黄金'):
        print(d['company'], json.dumps(d.get('investor_stances'), ensure_ascii=False))
