"""
Quick extraction for remaining PDFs (May, June, July)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pdfplumber
import pandas as pd
import os
import re

DATASET_DIR = r"d:\0SIHNEW\Dataset"
OUTPUT_DIR = r"d:\0SIHNEW\Dataset\extracted"
os.makedirs(OUTPUT_DIR, exist_ok=True)

pdf_files = sorted([f for f in os.listdir(DATASET_DIR) if f.endswith('.pdf')])
print(f"Found {len(pdf_files)} PDFs: {pdf_files}")

for pdf_file in pdf_files:
    # Check if already extracted
    base = os.path.splitext(pdf_file)[0]
    existing = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(base)]
    if len(existing) > 10:
        print(f"\n{pdf_file}: Already extracted ({len(existing)} files), skipping.")
        continue
    
    pdf_path = os.path.join(DATASET_DIR, pdf_file)
    print(f"\nExtracting: {pdf_file}...")
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"  Pages: {len(pdf.pages)}")
        table_count = 0
        
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                for t_idx, table in enumerate(tables):
                    if len(table) > 1:
                        header = [str(c).strip() if c else f'col_{j}' for j, c in enumerate(table[0])]
                        # Deduplicate headers
                        seen = {}
                        new_header = []
                        for h in header:
                            if h in seen:
                                seen[h] += 1
                                new_header.append(f"{h}_{seen[h]}")
                            else:
                                seen[h] = 0
                                new_header.append(h)
                        
                        data = table[1:]
                        df = pd.DataFrame(data, columns=new_header)
                        df['_source_page'] = i + 1
                        df['_source_file'] = pdf_file
                        
                        table_count += 1
                        output_file = os.path.join(OUTPUT_DIR, f"{base}_table_{table_count}.csv")
                        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"  Extracted {table_count} tables")

print("\nDone!")
