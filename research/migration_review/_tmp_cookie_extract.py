import re, pathlib
html=pathlib.Path('reports/联影医疗/sources/2026Q1.pdf').read_text(encoding='utf-8')
js=re.search(r'<script>(.*)</script>',html,re.S).group(1)
pathlib.Path('_tmp_sse_inner.js').write_text("var location={host:'www.sse.com.cn'};\nvar document={cookie:''};\n"+js+"\nconsole.log(document.cookie);\n",encoding='utf-8')
print(len(js), js[:80])
