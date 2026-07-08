from pathlib import Path
import pdfplumber
pages=[13,14,16,17,18,19,21,31,32,33,34,35,36,37,38,39,40,41,42,45,50,51,53,54,55,56,58,59,60,61,62,64,65,73,74,86,87,88,90,91,92,93,94,95,96,97,98,103,104,108,109,111,157,160,161,162,171,172,175,177,178,179,180,184,185]
with pdfplumber.open('_sources/annual_2025.pdf') as pdf:
    for n in pages:
        if n<=len(pdf.pages):
            t=pdf.pages[n-1].extract_text() or ''
            print(f'\n\n===== PAGE {n} =====')
            print(t[:3500])
