from pathlib import Path
import re
html=Path('sina_id_12011598.html')
# find file created
files=list(Path('.').glob('sina_*.html'))
print([f.name for f in files])
text=files[0].read_text(encoding='utf-8')
# strip scripts/styles tags, convert br
main=text
for pat in [r'<script.*?</script>',r'<style.*?</style>']:
    main=re.sub(pat,'',main,flags=re.S|re.I)
main=re.sub(r'<br\s*/?>','\n',main,flags=re.I)
main=re.sub(r'</p>|</tr>|</div>|</h\d>|</table>','\n',main,flags=re.I)
main=re.sub(r'<[^>]+>',' ',main)
main=re.sub(r'&nbsp;',' ',main)
main=re.sub(r'&lt;','<',main).replace('&gt;','>').replace('&amp;','&')
main=re.sub(r'[ \t\r\f\v]+',' ',main)
main=re.sub(r'\n\s+','\n',main)
Path('sina_2025_annual_12011598.txt').write_text(main,encoding='utf-8')
print('len',len(main))
for key in ['营业收入','分产品','电网自动化','电厂及工业自动化','国际业务','前五名客户']:
    print('\n--',key)
    for m in re.finditer(key, main):
        s=max(0,m.start()-300); e=min(len(main),m.end()+500)
        print(main[s:e].replace('\n',' ')[:1000]); break
