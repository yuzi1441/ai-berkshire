import re, pathlib, json
text=pathlib.Path('sources/2025AR_11972985.pdf.txt').read_text(encoding='utf-8',errors='ignore')
patterns=['分行业、分产品','营业收入构成','电力设备业务 2025 年','数控设备','电力工程','前五名客户','销售费用','直接、间接出口','世界前列','500kV','特高压','工信部','CHVT','MIII','市场地位','竞争优势','主要产品','业务板块','以销定产','小批量','高压','电网','变压器厂商','出口','印尼工厂','土耳其工厂','售后服务','客户认证','研发投入','专利','标准']
chunks=[]
for p in patterns:
 ms=list(re.finditer(p,text))
 for i,m in enumerate(ms[:5]):
  s=max(0,m.start()-500); e=min(len(text),m.end()+1000)
  chunks.append('\n---PATTERN %s #%d---\n%s' % (p,i+1,text[s:e].replace('\n',' ')))
pathlib.Path('sources/research_snips_business_utf8.txt').write_text('\n'.join(chunks),encoding='utf-8')
print('wrote', len(chunks))