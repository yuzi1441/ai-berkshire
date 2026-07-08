from pathlib import Path
import requests, pdfplumber
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
files={
 '2026_equity_distribution.pdf':'http://static.cninfo.com.cn/finalpage/2026-07-01/1225399607.PDF',
 '2026_related_tx_estimate.pdf':'http://static.cninfo.com.cn/finalpage/2026-01-16/1224935933.PDF',
 '2025_profit_distribution_notice.pdf':'http://static.cninfo.com.cn/finalpage/2026-04-24/1225161863.PDF',
 '2026_board_18.pdf':'http://static.cninfo.com.cn/finalpage/2026-04-29/1225233629.PDF',
}
base=Path('sources'); base.mkdir(exist_ok=True)
for name,url in files.items():
 p=base/name
 if not p.exists():
  r=requests.get(url,headers=headers,timeout=60)
  print(name,r.status_code,len(r.content))
  p.write_bytes(r.content)
 txt=p.with_suffix('.txt')
 if not txt.exists():
  outs=[]
  with pdfplumber.open(p) as pdf:
   for i,page in enumerate(pdf.pages,1):
    outs.append(f'\n---PAGE {i}---\n'+(page.extract_text() or ''))
  txt.write_text('\n'.join(outs),encoding='utf-8')
