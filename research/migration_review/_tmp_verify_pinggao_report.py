# -*- coding: utf-8 -*-
import json, subprocess, os, sys
from pathlib import Path
report=Path('reports/平高电气/平高电气-management-20260707.md')
text=report.read_text(encoding='utf-8')
checks={
 'title':'平高电气（600312.SH）管理层纵深研究' in text,
 'score':'3.75 / 5' in text,
 'sun':'孙继强' in text and '张国跃' in text,
 'dividend':'40.11%' in text,
 'valuation':'PE 21.37x' in text,
 'source_gap':'员工评价、客户非正式反馈公开资料不足' in text,
}
print(json.dumps(checks,ensure_ascii=False,indent=2))
print('all_ok', all(checks.values()))
# Count characters and extract key lines
for keyword in ['一句话结论','关键人物速览','诚信度评估','综合评分与结论','数据与验算附录']:
    print(keyword, text.find(keyword))
