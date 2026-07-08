from pathlib import Path
text=Path('sources/annual_key_pages.txt').read_text(encoding='utf-8')
print('len',len(text))
for key in ['境内水电','分行业','营业收入','上网电价','售电量','装机容量','业务概要']:
    idx=text.find(key)
    print('\nKEY',key,'IDX',idx)
    print(text[max(0,idx-300):idx+1200] if idx>=0 else 'not found')