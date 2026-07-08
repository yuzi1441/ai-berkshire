from decimal import Decimal, ROUND_HALF_UP
D=Decimal
data={
'2026Q1':{
'rev':D('8352015912'), 'rev_yoy':D('8237179005'), 'cogs':D('3184616660'), 'cogs_yoy':D('3086814486'),
'sales':D('1239689610'), 'admin':D('343826411'), 'rd':D('801738588'), 'fin':D('241041353'),
'np_parent':D('2329658005'), 'np_parent_yoy':D('2628580553'), 'deduct':D('2296470040'), 'deduct_yoy':D('2530581109'), 'ocf':D('1381035479'), 'ocf_yoy':D('1494408057'),
'ar':D('3574025664'), 'ar_start':D('3408119891'), 'inv':D('5254258350'), 'inv_start':D('5003717480'), 'cash':D('17792797168'), 'debt':D('324719')+D('272785'), 'liab':D('14769192004'), 'assets':D('59614755270'), 'equity_parent':D('40110091891'), 'contract':D('3342384074'), 'goodwill':D('11207360044'), 'shares':D('1212441394'),
},
'2025':{
'rev':D('33282159404'), 'rev_yoy':D('36725749548'), 'cogs':D('13207838172'), 'cogs_yoy':D('13547519384'),
'sales':D('5145135431'), 'admin':D('1550675756'), 'rd':D('3578692207'), 'fin':D('-262908161'),
'np_parent':D('8135775409'), 'np_parent_yoy':D('11668487164'), 'deduct':D('8068550808'), 'deduct_yoy':D('11442036083'), 'ocf':D('10144968535'), 'ocf_yoy':D('12432041281'),
'ar':D('3408119891'), 'ar_start':D('3219300494'), 'inv':D('5003717480'), 'inv_start':D('4757425283'), 'cash':D('17690372308'), 'debt':D('328106')+D('4062631'), 'liab':D('16255447654'), 'assets':D('59266767707'), 'equity_parent':D('38093330471'), 'contract':D('3000601014'), 'goodwill':D('11404095043'), 'shares':D('1212441394'), 'div_cash':D('5310000000')
}}
def pct(a,b): return (a/b*100).quantize(D('0.01'))
def yoy(a,b): return ((a/b-1)*100).quantize(D('0.01'))
def bny(x): return (x/D('100000000')).quantize(D('0.01'))
for k,v in data.items():
 print('\n',k)
 for metric in ['rev','np_parent','deduct','ocf']:
  if metric+'_yoy' in v: print(metric,'亿',bny(v[metric]),'yoy',yoy(v[metric],v[metric+'_yoy']))
 print('gross_margin', pct(v['rev']-v['cogs'],v['rev']))
 print('sales_rate', pct(v['sales'],v['rev']),'admin',pct(v['admin'],v['rev']),'rd',pct(v['rd'],v['rev']),'fin',pct(v['fin'],v['rev']))
 print('net_margin_parent',pct(v['np_parent'],v['rev']),'deduct_margin',pct(v['deduct'],v['rev']),'ocf/net',pct(v['ocf'],v['np_parent']))
 print('ar/rev',pct(v['ar'],v['rev']),'inv/rev',pct(v['inv'],v['rev']),'liab/assets',pct(v['liab'],v['assets']),'cash-debt bn', bny(v['cash']-v['debt']))
 print('contract bn',bny(v['contract']),'goodwill/assets',pct(v['goodwill'],v['assets']))
print('price marketcap calc', D('140.60')*D('1211399283')/D('100000000'), 'PE ttm using 2025+q1 delta', (D('140.60')*D('1211399283')/(data['2025']['np_parent']-D('2628580553')+D('2329658005'))).quantize(D('0.01')))
print('PE 2025', (D('140.60')*D('1211399283')/data['2025']['np_parent']).quantize(D('0.01')))
print('div yield 2025/marketcap', pct(data['2025']['div_cash'], D('140.60')*D('1211399283')))
