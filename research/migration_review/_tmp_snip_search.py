import pathlib,re
src=pathlib.Path('reports/联影医疗/sources')
text=(src/'2025Annual.txt').read_text(encoding='utf-8',errors='ignore')
patterns=['董事长','张强','首席执行官','薛敏','管理层讨论','前五名客户','前五名供应商','回购','现金分红','2025年度利润分配','研发投入','公司研发投入情况','市场份额','国内市场','全球','国家政策','竞争格局','GE','西门子','飞利浦','收入构成','主营业务分行业','主营业务分产品','产品分项','医学影像设备','放射治疗产品','联影智能','股份支付','商誉','募集资金','资产减值','存货跌价','应收账款','销售费用','研发费用']
for pat in patterns:
 print('\n###',pat)
 for m in list(re.finditer(pat,text))[:3]:
  s=max(0,m.start()-350); e=min(len(text),m.start()+1000)
  print(text[s:e].replace('\n',' ')[:1400])
  print('---')
