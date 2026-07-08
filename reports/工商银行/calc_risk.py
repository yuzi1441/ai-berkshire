from decimal import Decimal
# all RMB million unless noted
q1 = {
 'revenue': Decimal('230370'), 'revenue_yoy': Decimal('8.27'),
 'parent_np': Decimal('86941'), 'parent_np_yoy': Decimal('3.31'),
 'net_profit': Decimal('88013'), 'net_profit_yoy': Decimal('3.90'),
 'nii': Decimal('168531'), 'nii_yoy': Decimal('7.49'), 'nim': Decimal('1.29'),
 'non_interest': Decimal('61839'), 'non_interest_yoy': Decimal('10.45'),
 'fee': Decimal('40916'), 'fee_yoy': Decimal('5.24'),
 'impairment': Decimal('69446'), 'impairment_yoy': Decimal('21.55'),
 'loan_impairment': Decimal('66559'), 'loan_impairment_yoy': Decimal('16.27'),
 'loans': Decimal('31648252'), 'loan_inc': Decimal('1142138'), 'loan_growth': Decimal('3.74'),
 'corp': Decimal('19992688'), 'personal': Decimal('9058964'), 'bill': Decimal('2596600'),
 'deposits': Decimal('38587203'), 'deposit_growth': Decimal('3.42'),
 'time_dep': Decimal('23359800'), 'demand_dep': Decimal('14587096'),
 'npl': Decimal('413876'), 'npl_inc': Decimal('14863'), 'npl_rate': Decimal('1.31'),
 'coverage': Decimal('214.38'), 'cet1': Decimal('13.26'), 'tier1': Decimal('14.56'), 'car': Decimal('18.21'),
 'assets': Decimal('55772584'), 'assets_growth': Decimal('4.29'), 'equity': Decimal('4355759')
}
annual = {
 'npl_2025': Decimal('399013'), 'npl_2024': Decimal('379458'),
 'attention_2025': Decimal('594656'), 'attention_2024': Decimal('574171'),
 'overdue_2025': Decimal('462735'), 'overdue_2024': Decimal('406739'),
 'overdue90_2025': Decimal('136903')+Decimal('145087')+Decimal('50438'),
 'overdue90_2024': Decimal('120579')+Decimal('124646')+Decimal('39154'),
 'restructured_2025': Decimal('156027'), 'restructured_inc': Decimal('16941'),
 'mortgage_npl_2025': Decimal('62250'), 'mortgage_npl_2024': Decimal('44317'),
 'mortgage_loan_2025': Decimal('5875868'), 'mortgage_loan_2024': Decimal('6083180'),
 'personal_biz_npl_2025': Decimal('35088'), 'personal_biz_npl_2024': Decimal('21280'),
 'creditcard_npl_2025': Decimal('32122'), 'creditcard_npl_2024': Decimal('27173'),
 'realestate_loan_2025': Decimal('864576'), 'realestate_npl_2025': Decimal('46576'),
 'realestate_loan_2024': Decimal('880986'), 'realestate_npl_2024': Decimal('43964'),
 'stage2_loans_2025': Decimal('871568')+Decimal('2903'),
 'stage3_loans_2025': Decimal('398832')+Decimal('181'),
 'stage2_loans_2024': Decimal('795620')+Decimal('938'),
 'stage3_loans_2024': Decimal('379423')+Decimal('35'),
}
print('Q1 NPL inc %', (q1['npl_inc']/(q1['npl']-q1['npl_inc'])*100).quantize(Decimal('0.01')))
print('Q1 npl/parent np', (q1['npl_inc']/q1['parent_np']*100).quantize(Decimal('0.01')))
print('Q1 impairment/parent np', (q1['impairment']/q1['parent_np']*100).quantize(Decimal('0.01')))
print('Q1 loan impairment/parent np', (q1['loan_impairment']/q1['parent_np']*100).quantize(Decimal('0.01')))
print('Annual overdue increase %', ((annual['overdue_2025']-annual['overdue_2024'])/annual['overdue_2024']*100).quantize(Decimal('0.01')))
print('Annual overdue90 increase %', ((annual['overdue90_2025']-annual['overdue90_2024'])/annual['overdue90_2024']*100).quantize(Decimal('0.01')), annual['overdue90_2025'], annual['overdue90_2024'])
print('Mortgage balance change %', ((annual['mortgage_loan_2025']-annual['mortgage_loan_2024'])/annual['mortgage_loan_2024']*100).quantize(Decimal('0.01')))
print('Mortgage NPL increase %', ((annual['mortgage_npl_2025']-annual['mortgage_npl_2024'])/annual['mortgage_npl_2024']*100).quantize(Decimal('0.01')))
print('Personal business NPL increase %', ((annual['personal_biz_npl_2025']-annual['personal_biz_npl_2024'])/annual['personal_biz_npl_2024']*100).quantize(Decimal('0.01')))
print('Credit card NPL increase %', ((annual['creditcard_npl_2025']-annual['creditcard_npl_2024'])/annual['creditcard_npl_2024']*100).quantize(Decimal('0.01')))
print('Real estate npl rate computed', (annual['realestate_npl_2025']/annual['realestate_loan_2025']*100).quantize(Decimal('0.01')))
print('Real estate npl inc %', ((annual['realestate_npl_2025']-annual['realestate_npl_2024'])/annual['realestate_npl_2024']*100).quantize(Decimal('0.01')))
print('Stage2 loans inc %', ((annual['stage2_loans_2025']-annual['stage2_loans_2024'])/annual['stage2_loans_2024']*100).quantize(Decimal('0.01')), annual['stage2_loans_2025'])
print('Stage3 loans inc %', ((annual['stage3_loans_2025']-annual['stage3_loans_2024'])/annual['stage3_loans_2024']*100).quantize(Decimal('0.01')), annual['stage3_loans_2025'])
print('Q1 time deposit / deposits', (q1['time_dep']/q1['deposits']*100).quantize(Decimal('0.01')))
print('Q1 demand / deposits', (q1['demand_dep']/q1['deposits']*100).quantize(Decimal('0.01')))
print('Q1 investment growth vs loan growth', q1['assets_growth'])
