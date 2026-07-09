from decimal import Decimal, ROUND_HALF_UP
D=Decimal
total=D('9363074210.11')
segments={
'原料药及医药中间体':D('4476174150.95'),
'制剂':D('4622070569.31'),
'大健康':D('37989351.84'),
}
products={
'全身用抗感染药':D('1726402291.58'),
'心血管系统用药':D('705626352.95'),
'神经系统用药':D('516012001.27'),
'泌尿生殖系统用药及激素制剂':D('443183643.89'),
'骨骼肌肉系统用药':D('363102977.70'),
'消化道和新陈代谢用药':D('126584936.63'),
'抗肿瘤药及免疫调节剂':D('129945640.49'),
'血液和造血系统用药':D('101207657.72'),
'呼吸系统用药':D('186666193.60'),
}
regions={'海外地区':D('1908779401.00'),'华东地区':D('2350368812.14'),'华南地区':D('1250603579.67'),'华北地区':D('1184820742.94')}
sales={'直销':D('1891759304.83'),'经销':D('7326313642.82')}
def pct(x,base=total): return (x/base*100).quantize(D('0.1'), rounding=ROUND_HALF_UP)
print('Segments')
for k,v in segments.items(): print(k, float((v/D(10)**8).quantize(D('0.01'))), str(pct(v))+'%')
print('Sales model')
for k,v in sales.items(): print(k, float((v/D(10)**8).quantize(D('0.01'))), str(pct(v))+'%')
print('Products')
for k,v in products.items(): print(k, float((v/D(10)**8).quantize(D('0.01'))), str(pct(v))+'%')
print('Regions')
for k,v in regions.items(): print(k, float((v/D(10)**8).quantize(D('0.01'))), str(pct(v))+'%')
