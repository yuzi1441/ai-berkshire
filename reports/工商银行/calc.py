from decimal import Decimal, ROUND_HALF_UP
vals={'利息净收入':Decimal('635126'),'手续费及佣金净收入':Decimal('111171'),'营业收入':Decimal('838270'),'公司金融业务':Decimal('410676'),'个人金融业务':Decimal('327739'),'资金业务':Decimal('93990'),'其他':Decimal('5865')}
rev=vals['营业收入']
for k,v in vals.items():
    if k!='营业收入':
        print(k, (v/rev*100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
print('非息收入', ((rev-vals['利息净收入'])/rev*100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
print('手续费占', (vals['手续费及佣金净收入']/rev*100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
print('Q1净息占', (Decimal('168531')/Decimal('230370')*100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
print('Q1手续费占', (Decimal('40916')/Decimal('230370')*100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
