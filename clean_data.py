"""
PAIMANA Data Cleaning Pipeline
Takes raw extracted PDF tables and creates clean, ML-ready CSV files.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import os
import re
from datetime import datetime

EXTRACTED_DIR = r"d:\0SIHNEW\Dataset\extracted"
OUTPUT_DIR = r"d:\0SIHNEW\Dataset\cleaned"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_column_names(df):
    """Standardize column names by removing newlines and extra spaces."""
    new_cols = {}
    for col in df.columns:
        clean = col.replace('\n', ' ').replace('\r', ' ')
        clean = re.sub(r'\s+', ' ', clean).strip()
        new_cols[col] = clean
    return df.rename(columns=new_cols)


def is_project_table(df):
    """Check if a DataFrame is a project-level table (Table 6 format)."""
    cols_str = ' '.join(str(c).lower() for c in df.columns)
    return ('project name' in cols_str and 
            'state' in cols_str and 
            ('cost' in cols_str or 'expenditure' in cols_str))


def parse_cost_field(value):
    """Parse 'Original Cost\\nRevised Cost' into two separate values.
    Example: '265.91\\n(265.91)' -> (265.91, 265.91)
    """
    if pd.isna(value) or str(value).strip() == '':
        return np.nan, np.nan
    
    val = str(value).strip()
    # Remove commas from numbers
    val = val.replace(',', '')
    
    # Try to find two numbers: original and revised (in parentheses)
    # Pattern: number\n(number) or number\nnumber
    numbers = re.findall(r'[\d.]+', val)
    
    if len(numbers) >= 2:
        try:
            return float(numbers[0]), float(numbers[1])
        except ValueError:
            pass
    elif len(numbers) == 1:
        try:
            return float(numbers[0]), float(numbers[0])
        except ValueError:
            pass
    
    return np.nan, np.nan


def parse_date_field(value):
    """Parse 'Date1\\n(Date2)' into two dates.
    Example: '03/2023\\n(01/2024)' -> ('03/2023', '01/2024')
    """
    if pd.isna(value) or str(value).strip() in ('', '-'):
        return np.nan, np.nan
    
    val = str(value).strip()
    # Find all MM/YYYY patterns
    dates = re.findall(r'(\d{1,2}/\d{4})', val)
    
    if len(dates) >= 2:
        return dates[0], dates[1]
    elif len(dates) == 1:
        return dates[0], np.nan
    
    return np.nan, np.nan


def parse_project_name(value):
    """Parse project name field to extract name, agency, project code.
    Example: 'Project Name\\n(Agency)\\n(Code)\\n(Legacy) (PMGID)'
    """
    if pd.isna(value) or str(value).strip() == '':
        return '', '', ''
    
    val = str(value).strip()
    
    # Extract project code - look for patterns like (612786) or (N04000106)
    codes = re.findall(r'\(([A-Z]?\d{5,})\)', val)
    project_code = codes[0] if codes else ''
    
    # Extract agency - usually in first parentheses with text
    agency_match = re.findall(r'\(([A-Za-z][^)]{3,})\)', val)
    agency = agency_match[0] if agency_match else ''
    
    # Project name - everything before the first newline or first parenthesis
    name = val.split('\n')[0].strip()
    # If name is too long, truncate at a reasonable point
    if len(name) > 200:
        name = name[:200]
    
    return name, agency, project_code


def parse_numeric(value):
    """Parse a numeric value, handling commas and special characters."""
    if pd.isna(value) or str(value).strip() in ('', '-', 'NA', 'N/A'):
        return np.nan
    val = str(value).strip().replace(',', '')
    try:
        return float(val)
    except ValueError:
        # Try to extract first number
        nums = re.findall(r'[\d.]+', val)
        if nums:
            try:
                return float(nums[0])
            except ValueError:
                pass
    return np.nan


def identify_ministry_sector(tables_by_page, project_page):
    """Try to identify ministry and sector from the table structure.
    Ministry/sector headers appear as rows with NaN Sl.No."""
    # This is a heuristic - the PDF tables have ministry/sector as header rows
    pass


def process_project_tables(pdf_basename):
    """Process all project-level tables from a single PDF into one clean DataFrame."""
    
    # Find all individual table files for this PDF
    table_files = sorted([
        f for f in os.listdir(EXTRACTED_DIR) 
        if f.startswith(pdf_basename) and '_table_' in f and f.endswith('.csv')
    ], key=lambda x: int(re.search(r'_table_(\d+)', x).group(1)))
    
    all_projects = []
    current_ministry = ''
    current_sector = ''
    
    for table_file in table_files:
        filepath = os.path.join(EXTRACTED_DIR, table_file)
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
        except Exception as e:
            continue
        
        df = clean_column_names(df)
        
        if not is_project_table(df):
            continue
        
        # Process each row
        for _, row in df.iterrows():
            row_dict = {str(k): v for k, v in row.items()}
            
            # Find the relevant columns by partial matching
            sl_col = [c for c in row_dict if 'sl' in c.lower() and 'no' in c.lower()]
            name_col = [c for c in row_dict if 'project name' in c.lower()]
            state_col = [c for c in row_dict if 'state' in c.lower()]
            approval_col = [c for c in row_dict if 'approval' in c.lower() or 'start date' in c.lower()]
            doc_col = [c for c in row_dict if 'doc' in c.lower() or 'completion' in c.lower()]
            cost_col = [c for c in row_dict if 'cost' in c.lower() and 'revised' in c.lower()]
            expend_col = [c for c in row_dict if 'expenditure' in c.lower()]
            progress_col = [c for c in row_dict if 'progress' in c.lower() or 'physical' in c.lower()]
            
            sl_val = row_dict.get(sl_col[0]) if sl_col else np.nan
            
            # Check if this is a ministry/sector header row (Sl.No is NaN)
            if pd.isna(sl_val) or str(sl_val).strip() == '':
                name_val = row_dict.get(name_col[0], '') if name_col else ''
                if isinstance(name_val, str) and name_val.strip():
                    text = name_val.strip()
                    if 'ministry' in text.lower() or 'department' in text.lower():
                        current_ministry = text
                    elif len(text) < 80:  # Likely a sector name
                        current_sector = text
                continue
            
            # Parse project data
            name_raw = row_dict.get(name_col[0], '') if name_col else ''
            project_name, agency, project_code = parse_project_name(name_raw)
            
            state = row_dict.get(state_col[0], '') if state_col else ''
            
            # Parse dates
            approval_raw = row_dict.get(approval_col[0], '') if approval_col else ''
            approval_date, start_date = parse_date_field(approval_raw)
            
            doc_raw = row_dict.get(doc_col[0], '') if doc_col else ''
            target_doc, revised_doc = parse_date_field(doc_raw)
            
            # Parse costs
            cost_raw = row_dict.get(cost_col[0], '') if cost_col else ''
            original_cost, revised_cost = parse_cost_field(cost_raw)
            
            # Parse expenditure
            expend_raw = row_dict.get(expend_col[0], '') if expend_col else np.nan
            expenditure = parse_numeric(expend_raw)
            
            # Parse physical progress
            progress_raw = row_dict.get(progress_col[0], '') if progress_col else np.nan
            physical_progress = parse_numeric(progress_raw)
            
            project = {
                'sl_no': parse_numeric(sl_val),
                'project_name': project_name,
                'agency': agency,
                'project_code': project_code,
                'ministry': current_ministry,
                'sector': current_sector,
                'state': str(state).strip() if not pd.isna(state) else '',
                'approval_date': approval_date,
                'start_date': start_date,
                'target_completion_date': target_doc,
                'revised_completion_date': revised_doc,
                'original_cost_cr': original_cost,
                'revised_cost_cr': revised_cost,
                'cumulative_expenditure_cr': expenditure,
                'physical_progress_pct': physical_progress,
                'source_file': pdf_basename,
            }
            all_projects.append(project)
    
    return pd.DataFrame(all_projects)


def add_derived_features(df):
    """Add computed features useful for ML models."""
    
    # Cost overrun ratio
    df['cost_overrun_ratio'] = np.where(
        df['original_cost_cr'] > 0,
        df['revised_cost_cr'] / df['original_cost_cr'],
        np.nan
    )
    
    # Cost overrun percentage
    df['cost_overrun_pct'] = (df['cost_overrun_ratio'] - 1) * 100
    
    # Has cost overrun (binary)
    df['has_cost_overrun'] = (df['cost_overrun_ratio'] > 1.0).astype(int)
    
    # Expenditure ratio (how much of budget spent)
    df['expenditure_ratio'] = np.where(
        df['revised_cost_cr'] > 0,
        df['cumulative_expenditure_cr'] / df['revised_cost_cr'],
        np.nan
    )
    
    # Financial progress (expenditure / original cost)
    df['financial_progress_pct'] = np.where(
        df['original_cost_cr'] > 0,
        (df['cumulative_expenditure_cr'] / df['original_cost_cr']) * 100,
        np.nan
    )
    
    # Physical-Financial gap
    df['physical_financial_gap'] = df['physical_progress_pct'] - df['financial_progress_pct']
    
    # Parse dates for time calculations
    def parse_mmyyyy(val):
        if pd.isna(val) or str(val).strip() in ('', '-'):
            return pd.NaT
        try:
            return pd.to_datetime(val, format='%m/%Y')
        except:
            return pd.NaT
    
    df['approval_date_parsed'] = df['approval_date'].apply(parse_mmyyyy)
    df['start_date_parsed'] = df['start_date'].apply(parse_mmyyyy)
    df['target_completion_parsed'] = df['target_completion_date'].apply(parse_mmyyyy)
    df['revised_completion_parsed'] = df['revised_completion_date'].apply(parse_mmyyyy)
    
    # Project duration (planned, in months)
    df['planned_duration_months'] = (
        (df['target_completion_parsed'] - df['start_date_parsed']).dt.days / 30.44
    ).round(1)
    
    # Time overrun in months
    df['time_overrun_months'] = (
        (df['revised_completion_parsed'] - df['target_completion_parsed']).dt.days / 30.44
    ).round(1)
    
    # Has time overrun (binary)
    df['has_time_overrun'] = (df['time_overrun_months'] > 0).astype(int)
    
    # Project age from approval to now (months)
    now = pd.Timestamp.now()
    df['project_age_months'] = (
        (now - df['approval_date_parsed']).dt.days / 30.44
    ).round(1)
    
    # Time elapsed ratio (how far along in timeline)
    total_planned = (df['target_completion_parsed'] - df['start_date_parsed']).dt.days
    elapsed = (now - df['start_date_parsed']).dt.days
    df['time_elapsed_ratio'] = np.where(total_planned > 0, elapsed / total_planned, np.nan)
    
    # Cost bucket
    df['cost_bucket'] = pd.cut(
        df['original_cost_cr'],
        bins=[0, 500, 1000, 5000, 10000, 50000, float('inf')],
        labels=['150-500 Cr', '500-1000 Cr', '1000-5000 Cr', '5000-10000 Cr', '10000-50000 Cr', '50000+ Cr']
    )
    
    return df


if __name__ == "__main__":
    # Get unique PDF basenames
    pdf_files = sorted(set(
        f.split('_table_')[0] + '.pdf' if '_table_' in f else f.split('_combined_')[0] + '.pdf'
        for f in os.listdir(EXTRACTED_DIR) if f.endswith('.csv')
    ))
    # Extract just the base name without .pdf
    basenames = sorted(set(
        f.replace('.pdf', '') for f in pdf_files
    ))
    
    print(f"Processing {len(basenames)} Flash Reports: {basenames}")
    
    all_months = []
    
    for basename in basenames:
        print(f"\n{'='*60}")
        print(f"Processing: {basename}")
        print(f"{'='*60}")
        
        df = process_project_tables(basename)
        
        if len(df) > 0:
            print(f"  Raw projects extracted: {len(df)}")
            
            # Remove rows where project_name is empty
            df = df[df['project_name'].str.strip() != '']
            print(f"  After removing empty names: {len(df)}")
            
            # Add month identifier
            month_match = re.search(r'(April|May|June|July|August|September|October|November|December|January|February|March)', basename, re.IGNORECASE)
            year_match = re.search(r'(\d{4})', basename)
            df['report_month'] = month_match.group(1) if month_match else 'Unknown'
            df['report_year'] = int(year_match.group(1)) if year_match else 2026
            
            # Add derived features
            df = add_derived_features(df)
            
            # Save individual month
            output_file = os.path.join(OUTPUT_DIR, f"{basename}_cleaned.csv")
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"  Saved: {output_file}")
            
            all_months.append(df)
            
            # Print summary stats
            print(f"\n  --- Summary ---")
            print(f"  Total projects: {len(df)}")
            print(f"  States: {df['state'].nunique()}")
            print(f"  Ministries: {df['ministry'].nunique()}")
            print(f"  Sectors: {df['sector'].nunique()}")
            print(f"  Avg original cost: {df['original_cost_cr'].mean():.2f} Cr")
            print(f"  Avg revised cost: {df['revised_cost_cr'].mean():.2f} Cr")
            print(f"  Projects with cost overrun: {df['has_cost_overrun'].sum()} ({df['has_cost_overrun'].mean()*100:.1f}%)")
            print(f"  Projects with time overrun: {df['has_time_overrun'].sum()} ({df['has_time_overrun'].mean()*100:.1f}%)")
            print(f"  Avg physical progress: {df['physical_progress_pct'].mean():.1f}%")
        else:
            print(f"  No project data found!")
    
    # Combine all months
    if all_months:
        master = pd.concat(all_months, ignore_index=True)
        master_file = os.path.join(OUTPUT_DIR, "all_projects_master.csv")
        master.to_csv(master_file, index=False, encoding='utf-8-sig')
        print(f"\n\n{'='*60}")
        print(f"MASTER DATASET SAVED: {master_file}")
        print(f"Total rows: {len(master)}")
        print(f"Columns: {list(master.columns)}")
        print(f"{'='*60}")
