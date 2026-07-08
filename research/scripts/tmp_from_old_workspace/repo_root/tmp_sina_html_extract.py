import requests, re, json, pathlib
ids={'2026Q1':'12277344','2025AR':'12011598'}
out=pathlib.Path('reports')/'四方股份'/'sources'
for key,id in ids.items():
    url=f'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id={id}&stockid=601126'
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=30)
    text=r.content.decode('gb18030','replace')
    # extract title and some text paragraphs after blk_container
    title=re.search(r'<title>(.*?)</title>',text,re.S)
    body=re.sub(r'<script.*?</script>|<style.*?</style>','',text,flags=re.S)
    body=re.sub(r'<[^>]+>','\n',body)
    body=re.sub(r'\n{2,}','\n',body)
    (out/f'{key}_sina_html.txt').write_text(body,encoding='utf-8')
    print(key, title.group(1) if title else '', len(body))