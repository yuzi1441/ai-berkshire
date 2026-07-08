import pdfplumber
for fn in ['2026_board_election_exec_1225393424.PDF','2026_buyback_result_1225371122.PDF','2026_transformer_expansion_1225373731.PDF','2026_rugao_expansion_1225349917.PDF','2025_dividend_impl_1225399910.PDF','2026_q1_1225177123.PDF','2026_exec_reduction_1225306674.PDF','2026_exec_reduction2_1225385724.PDF']:
 print('\n====',fn,'====')
 pdf=pdfplumber.open('data/source/siyuan/'+fn)
 print('pages',len(pdf.pages))
 for i,p in enumerate(pdf.pages[:8]):
  text=p.extract_text() or ''
  print('\n---p',i+1,'---')
  print(text[:2000])