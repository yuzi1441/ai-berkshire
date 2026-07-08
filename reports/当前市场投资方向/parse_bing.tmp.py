from pathlib import Path
import re, html
s=Path('bing.tmp.html').read_text(encoding='utf-8',errors='ignore')
for m in re.finditer(r'<li class="b_algo".*?</li>', s, re.S):
    block=m.group(0)
    title=re.search(r'<h2.*?>(.*?)</h2>', block, re.S)
    link=re.search(r'<a href="(http[^"]+)"', block)
    desc=re.search(r'<p>(.*?)</p>', block, re.S)
    if title and link:
        clean=lambda x: re.sub('<.*?>','',html.unescape(x)).strip()
        print(clean(title.group(1)))
        print(html.unescape(link.group(1)))
        if desc: print(clean(desc.group(1)))
        print('---')
