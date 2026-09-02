"""
PDF Data Extraction Script for PAIMANA Flash Reports
Extracts tabular data from Flash Report PDFs and saves as CSV
"""
import pdfplumber
import pandas as pd
import os
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATASET_DIR = r"d:\0SIHNEW\Dataset"
OUTPUT_DIR = r"d:\0SIHNEW\Dataset\extracted"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def explore_pdf(pdf_path, max_pages=10):
    """Explore a PDF to understand its structure."""
    filename = os.path.basename(pdf_path)
    print(f"\n{'='*80}")
    print(f"EXPLORING: {filename}")
    print(f"{'='*80}")
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        for i, page in enumerate(pdf.pages[:max_pages]):
            print(f"\n--- Page {i+1} ---")
            
            # Extract text
            text = page.extract_text()
            if text:
                preview = text[:300].replace('\n', ' | ')
                print(f"Text: {preview}")
            
            # Extract tables
            tables = page.extract_tables()
            if tables:
                print(f"Tables found: {len(tables)}")
                for t_idx, table in enumerate(tables):
                    ncols = len(table[0]) if table and table[0] else 0
                    print(f"  Table {t_idx+1}: {len(table)} rows x {ncols} cols")
                    if table and len(table) > 0:
                        # Print header
                        header = [str(c)[:30] if c else '' for c in table[0]]
                        print(f"    Header: {header}")
            else:
                print("No tables on this page.")

def extract_all_tables(pdf_path):
    """Extract ALL tables from a PDF and return as list of DataFrames."""
    filename = os.path.basename(pdf_path)
    all_tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"\nExtracting from {filename} ({len(pdf.pages)} pages)...")
        
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                for t_idx, table in enumerate(tables):
                    if len(table) > 1:
                        header = [str(c).strip() if c else f'col_{j}' for j, c in enumerate(table[0])]
                        # Handle duplicate column names
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
                        df['_source_file'] = filename
                        all_tables.append(df)
                        print(f"  Page {i+1}, Table {t_idx+1}: {len(data)} rows x {len(new_header)} cols | Header: {new_header[:5]}...")
    
    return all_tables


def combine_similar_tables(tables):
    """Group and combine tables that share the same column structure."""
    if not tables:
        return {}
    
    groups = {}
    for df in tables:
        # Create a key from column names (excluding metadata cols)
        cols = [c for c in df.columns if not c.startswith('_source')]
        key = '|'.join(cols)
        if key not in groups:
            groups[key] = []
        groups[key].append(df)
    
    combined = {}
    for key, dfs in groups.items():
        combined_df = pd.concat(dfs, ignore_index=True)
        # Use first few column names as identifier
        cols = key.split('|')
        name = '_'.join(cols[:3]).replace(' ', '_').replace('/', '_')[:50]
        combined[name] = combined_df
        print(f"  Combined group '{name}': {len(dfs)} tables -> {len(combined_df)} rows, cols: {cols[:5]}")
    
    return combined


if __name__ == "__main__":
    pdf_files = sorted([f for f in os.listdir(DATASET_DIR) if f.endswith('.pdf')])
    print(f"Found {len(pdf_files)} PDF files: {pdf_files}")
    
    # Step 1: Explore first PDF structure (first 10 pages)
    if pdf_files:
        first_pdf = os.path.join(DATASET_DIR, pdf_files[0])
        explore_pdf(first_pdf, max_pages=10)
    
    # Step 2: Extract all tables from all PDFs
    print(f"\n\n{'='*80}")
    print("FULL EXTRACTION")
    print(f"{'='*80}")
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(DATASET_DIR, pdf_file)
        tables = extract_all_tables(pdf_path)
        base_name = os.path.splitext(pdf_file)[0]
        
        if tables:
            # Save individual tables
            for idx, df in enumerate(tables):
                output_file = os.path.join(OUTPUT_DIR, f"{base_name}_table_{idx+1}.csv")
                df.to_csv(output_file, index=False, encoding='utf-8-sig')
            
            # Combine similar tables
            print(f"\n  Combining similar tables from {pdf_file}:")
            combined = combine_similar_tables(tables)
            for name, df in combined.items():
                output_file = os.path.join(OUTPUT_DIR, f"{base_name}_combined_{name[:40]}.csv")
                df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"    Saved: {os.path.basename(output_file)} ({len(df)} rows)")
        else:
            print(f"  No tables found in {pdf_file}")
    
    print("\n\nDone! Check the 'extracted' folder.")
    
    # Step 3: Quick summary of extracted data
    print(f"\n{'='*80}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*80}")
    extracted_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.csv')]
    print(f"Total CSV files created: {len(extracted_files)}")
    for f in sorted(extracted_files):
        fpath = os.path.join(OUTPUT_DIR, f)
        df = pd.read_csv(fpath, encoding='utf-8-sig', nrows=2)
        print(f"  {f}: {len(pd.read_csv(fpath, encoding='utf-8-sig'))} rows x {len(df.columns)} cols")
