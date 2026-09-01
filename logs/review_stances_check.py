import json

with open(r'data\investment-dashboard\decision_board.json', encoding='utf-8') as f:
    data = json.load(f)

targets = ['中国神华', '特变电工', '东方电缆', '湖南黄金', '五粮液', '恒瑞医疗', '一拖股份',
           '江波龙', '宇视科技', '厦门钨业', '迈瑞医疗', '华明装备', '平安集团', '格力电器',
           '汾酒', '泸州老窖', '中国西电', '国药现代', '天坛生物', '工商银行', '思源电气',
           '深南电路', '智元机器人', '赛力斯', '阳光电源', '领益智造', '藏格矿业', '许继电气',
           '联影医疗', '美的集团', '茅台', '百济神州', '生益科技', 'CMOC', 'DapuStor',
           'Goldwind', 'chuanrun', 'chunfeng-dongli', 'BYD', 'focus-media', 'hgtech',
           'jingfang-keji', 'leaderdrive', 'montage-tech', '中国广核']
for d in data['decisions']:
    if d['company'] in targets:
        stances = d.get('investor_stances') or []
        print(d['company'], '| stances:', len(stances), '| summary:', (d.get('conclusion_summary') or '')[:50])
