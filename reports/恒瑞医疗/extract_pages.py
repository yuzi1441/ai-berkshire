from pypdf import PdfReader
r=PdfReader('source_pdfs/hengrui_2025_annual.pdf')
for pg in [6,19,20,21,22,23,58,61,66,67,68,69,82,83,92,93,94,95,114,115,122,123,124,125,126,127,128,129,130,131,132,135,136,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154]:
    txt=(r.pages[pg-1].extract_text() or '').replace('\n',' ')
    print(f'\n---PAGE {pg}---\n{txt[:2200]}')