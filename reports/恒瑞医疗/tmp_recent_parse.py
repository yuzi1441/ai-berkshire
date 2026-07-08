import re
from pathlib import Path
text=Path('recent_announcements_text.txt').read_text(encoding='utf-8')
# split by ###
for block in text.split('\n### ')[1:]:
    title=block.split('\n',1)[0]
    drug=re.search(r'药(?:物|品)?名称[:：]?\s*([^\n。]+?)(?:剂\s*型|申请事项|受\s*理|\s{2,}|$)', block)
    basics=[]
    for pat in [r'药品名称\s+([^\n]+?)\s+剂型', r'药物名称[:：]\s*([^\n]+)', r'关于\s*([^\s，]+?)\s*的《药物临床试验批准通知书》', r'关于([^\s，]+?)的《药物临床试验批准通知书》']:
        m=re.search(pat, block)
        if m: basics.append(m.group(1).strip())
    other=''
    m=re.search(r'二、药[物品]的其他情况(.+?)三、风险提示', block, re.S)
    if m: other=m.group(1).strip().replace('\n',' ')[:600]
    approv=''
    m=re.search(r'审批结论[:：]?(.+?)(?:二、|药品名称|一、药)', block, re.S)
    if m: approv=m.group(1).strip().replace('\n',' ')[:300]
    print('\nTITLE:',title)
    print('BASICS:', basics[:2])
    print('APPROV:', approv[:300])
    print('OTHER:', other[:600])
