import json
import re
from pathlib import Path

with open(r'data\investment-dashboard\decision_board.json', encoding='utf-8') as f:
    data = json.load(f)

# patterns that suggest the "main report" is actually a chapter file, not a final report
chapter_pat = re.compile(r'\d{2}-[^/]+\.md$')
suspects = []
for d in data['decisions']:
    reasons = []
    path = d.get('report_path', '')
    if d.get('action') in ('', None, '未提取'):
        reasons.append('action_missing')
    if chapter_pat.search(path):
        reasons.append('chapter_file_as_main')
    if '被排除' in path:
        reasons.append('excluded_folder')
    if d.get('company') in ('散户乙', 'pingan', '大师持仓追踪', '小米', '小米集团', 'Alibaba', '阿里巴巴', '百度', '百度集团', '紫金矿业', '洛阳钼业', '中国平安', '平安集团', 'BYD', '比亚迪', 'Yangtze-Power', '长江电力', '海尔智家'):
        reasons.append('possible_duplicate_entity')
    if reasons:
        suspects.append((d.get('company'), d.get('ticker'), d.get('action'), d.get('report_path'), ';'.join(reasons)))

for row in suspects:
    print(' | '.join(str(x) for x in row))
print('---')
print('total suspects:', len(suspects))
print('total decisions:', len(data['decisions']))
