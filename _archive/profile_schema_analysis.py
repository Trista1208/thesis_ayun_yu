#!/usr/bin/env python3
"""
Profiling Schema and Relationship Analysis

This script explores relationships between categories in the profiling schema
and calculates measures such as mutual information to identify meaningful correlations.
"""

import os
import sys
import json
import glob
import numpy as np
import pandas as pd
from datetime import datetime

try:
    from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
    from sklearn.preprocessing import LabelEncoder
    import warnings
    warnings.filterwarnings('ignore')
except ImportError as e:
    print("=" * 70)
    print("ERROR: Missing required packages!")
    print("=" * 70)
    print(f"Error: {e}")
    print("\nPlease install scikit-learn:")
    print("  pip install scikit-learn")
    sys.exit(1)

try:
    import openpyxl
except ImportError:
    pass


# Columns that should never be used in correlations / MI
# These are identifiers or profile fields that don't represent meaningful health metrics
EXCLUDED_ID_COLUMNS = {
    "Customer ID (unique identifier)",
    "Customer ID",
    "ID",
    "id",
    "customer_id",
    "customer id",
}

def is_excluded_column(col_name):
    """Check if a column should be excluded from correlation/MI analysis."""
    if not col_name:
        return True
    col_lower = str(col_name).lower().strip()
    # Exact matches
    if col_lower in EXCLUDED_ID_COLUMNS:
        return True
    # Pattern matches - exclude anything that looks like an ID
    if col_lower.endswith(" id") or col_lower.endswith("_id"):
        return True
    if "unique identifier" in col_lower:
        return True
    if col_lower == "id":
        return True
    return False


def load_parameter_dictionary():
    """Load the parameter dictionary."""
    # Priority order: cleaned > updated > timestamped > original
    # Check in output directory first, then fallback to root
    output_dir = "output"
    
    # 1. Try to find cleaned dictionary (preferred)
    cleaned_dicts = glob.glob(os.path.join(output_dir, "parameter_dictionary_*_cleaned.json"))
    if not cleaned_dicts:
        cleaned_dicts = glob.glob("parameter_dictionary_*_cleaned.json")
    if cleaned_dicts:
        cleaned_dicts.sort(key=os.path.getmtime, reverse=True)
        dict_file = cleaned_dicts[0]
        print(f"   Found cleaned dictionary: {dict_file}")
        with open(dict_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 2. Try to find updated dictionary
    updated_dicts = glob.glob(os.path.join(output_dir, "parameter_dictionary_updated_*.json"))
    if not updated_dicts:
        updated_dicts = glob.glob("parameter_dictionary_updated_*.json")
    if updated_dicts:
        updated_dicts.sort(key=os.path.getmtime, reverse=True)
        dict_file = updated_dicts[0]
        print(f"   Found updated dictionary: {dict_file}")
        with open(dict_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 3. Try to find any timestamped dictionary
    all_dicts = glob.glob(os.path.join(output_dir, "parameter_dictionary_*.json"))
    if not all_dicts:
        all_dicts = glob.glob("parameter_dictionary_*.json")
    if all_dicts:
        all_dicts.sort(key=os.path.getmtime, reverse=True)
        dict_file = all_dicts[0]
        print(f"   Found dictionary: {dict_file}")
        with open(dict_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 4. No dictionary found
    raise FileNotFoundError(
        "Parameter dictionary not found.\n"
        "Please run create_parameter_dictionary.py first to create a dictionary."
    )


def load_health_data():
    """Load health data from Excel file."""
    file_path = "health_export_29.10.2025 10_19.xlsx"
    
    # Read raw file to get column names
    df_raw = pd.read_excel(file_path, header=None)
    section_headers = df_raw.iloc[0].values.tolist()
    actual_column_names = df_raw.iloc[1].values.tolist()
    
    # Read data starting from row 2
    df = pd.read_excel(file_path, header=1)
    
    # Rename columns with actual names
    df.columns = [str(name).strip() if pd.notna(name) else f"Column_{i}" 
                  for i, name in enumerate(actual_column_names)]
    
    return df, section_headers, actual_column_names


def categorize_columns(df, param_dict):
    """Categorize columns by their sections."""
    sections = param_dict['sections']
    categorized = {}
    
    for section_name, param_list in sections.items():
        categorized[section_name] = []
        for param_name in param_list:
            if param_name in df.columns:
                categorized[section_name].append(param_name)
    
    return categorized


def prepare_numeric_data(df, columns):
    """Prepare numeric data for analysis, handling missing values."""
    # Filter to only columns that exist
    existing_cols = [col for col in columns if col in df.columns]
    if not existing_cols:
        return pd.DataFrame()
    
    data = df[existing_cols].copy()
    
    # Convert to numeric, coercing errors to NaN
    for col in list(data.columns):
        col_data = data[col]
        # Handle duplicate column names returning a DataFrame
        if isinstance(col_data, pd.DataFrame):
            if col_data.shape[1] == 0:
                data.drop(columns=[col], inplace=True)
                continue
            col_data = col_data.iloc[:, 0]
        data[col] = pd.to_numeric(col_data, errors='coerce')
    
    # Remove columns with too many missing values (>50%)
    valid_cols = data.columns[data.isnull().sum() < len(data) * 0.5]
    if len(valid_cols) == 0:
        return pd.DataFrame()
    
    data = data[valid_cols]
    
    return data


def calculate_section_statistics(df, categorized):
    """Calculate basic statistics and missingness for each section and variable."""
    stats = {}

    for section_name, columns in categorized.items():
        # Keep only columns that actually exist in the dataframe
        section_cols = [col for col in columns if col in df.columns]

        if not section_cols:
            stats[section_name] = {
                "num_variables": 0,
                "num_observations": 0,
                "missing_percentage": 0.0,
                "variables": [],
                "numeric_variables": [],
                "variables_detail": {},
            }
            continue

        section_df = df[section_cols]

        # Number of observations = rows with at least one non-missing value in this section
        num_observations = int(section_df.dropna(how="all").shape[0])

        total_cells = section_df.shape[0] * section_df.shape[1]
        missing_cells = int(section_df.isnull().sum().sum())
        missing_percentage = (missing_cells / total_cells) * 100 if total_cells > 0 else 0.0

        variables_detail = {}
        numeric_variables = []

        for col in section_cols:
            col_data = section_df[col]
            # If there are duplicate column names, pandas may return a DataFrame
            # In that case, use the first matching column as a representative
            if isinstance(col_data, pd.DataFrame):
                if col_data.shape[1] == 0:
                    continue
                col_data = col_data.iloc[:, 0]
            non_missing = int(col_data.notna().sum())
            missing = int(col_data.isna().sum())
            col_missing_pct = (missing / len(section_df)) * 100 if len(section_df) > 0 else 0.0

            # Try numeric conversion for descriptive stats
            numeric_data = pd.to_numeric(col_data, errors="coerce")
            is_numeric = numeric_data.notna().sum() > 0

            var_stats = {
                "is_numeric": bool(is_numeric),
                "non_missing_count": non_missing,
                "missing_count": missing,
                "missing_percentage": col_missing_pct,
            }

            if is_numeric:
                numeric_variables.append(col)
                valid = numeric_data.dropna()
                if len(valid) > 0:
                    var_stats.update(
                        {
                            "mean": float(valid.mean()),
                            "std": float(valid.std()) if len(valid) > 1 else 0.0,
                            "min": float(valid.min()),
                            "max": float(valid.max()),
                            "median": float(valid.median()),
                        }
                    )

            variables_detail[col] = var_stats

        stats[section_name] = {
            "num_variables": len(section_cols),
            "num_observations": num_observations,
            "missing_percentage": missing_percentage,
            # All variables in this section
            "variables": section_cols,
            # Only numeric variables used for correlations / MI
            "numeric_variables": numeric_variables,
            # Per-variable detail including missingness and numeric stats
            "variables_detail": variables_detail,
        }

    return stats


def calculate_cross_section_correlations(df, categorized, stats):
    """Calculate correlations between sections with optimized pairwise computation."""
    correlations = {}
    
    sections = list(categorized.keys())
    min_data_points = 10  # Minimum data points required for reliable correlation
    min_corr_threshold = 0.001  # Minimum correlation to report
    
    def _numeric_vars(section_name):
        """Helper to get numeric, non-ID variables for a section."""
        vars_list = stats[section_name].get("numeric_variables", [])
        clean = []
        for v in vars_list:
            if is_excluded_column(v):
                continue
            clean.append(v)
        return clean

    total_pairs = sum(
        len(_numeric_vars(s1)) * len(_numeric_vars(s2))
        for i, s1 in enumerate(sections)
        for s2 in sections[i + 1 :]
    )
    processed = 0
    
    for i, section1 in enumerate(sections):
        for section2 in sections[i + 1 :]:
            vars1 = _numeric_vars(section1)
            vars2 = _numeric_vars(section2)
            
            if not vars1 or not vars2:
                continue
            
            # Calculate correlations pairwise for each variable pair
            # This is more robust to missing data
            cross_corrs = []
            
            for v1 in vars1:
                if v1 not in df.columns:
                    continue
                # Double-check exclusion (defense in depth)
                if is_excluded_column(v1):
                    continue
                
                # Convert to numeric once per variable, handling duplicate names
                col1 = df[v1]
                if isinstance(col1, pd.DataFrame):
                    if col1.shape[1] == 0:
                        continue
                    col1 = col1.iloc[:, 0]
                data1 = pd.to_numeric(col1, errors='coerce')
                valid_count1 = data1.notna().sum()
                
                if valid_count1 < min_data_points:
                    continue
                
                for v2 in vars2:
                    if v2 not in df.columns or v1 == v2:
                        continue
                    # Double-check exclusion (defense in depth)
                    if is_excluded_column(v2):
                        continue
                    
                    processed += 1
                    if processed % 100 == 0:
                        print(f"   Processing correlations: {processed}/{total_pairs} pairs...", end='\r')
                    
                    # Convert to numeric
                    col2 = df[v2]
                    if isinstance(col2, pd.DataFrame):
                        if col2.shape[1] == 0:
                            continue
                        col2 = col2.iloc[:, 0]
                    data2 = pd.to_numeric(col2, errors='coerce')
                    valid_count2 = data2.notna().sum()
                    
                    if valid_count2 < min_data_points:
                        continue
                    
                    # Calculate pairwise correlation using complete cases
                    try:
                        # Use pairwise deletion for correlation
                        pair_data = pd.DataFrame({v1: data1, v2: data2}).dropna()
                        
                        if len(pair_data) < min_data_points:
                            continue
                        
                        # Calculate Pearson correlation
                        corr_val = pair_data[v1].corr(pair_data[v2])
                        
                        if not pd.isna(corr_val) and abs(corr_val) > min_corr_threshold:
                            cross_corrs.append({
                                'var1': v1,
                                'var2': v2,
                                'correlation': float(corr_val),
                                'n_observations': len(pair_data),
                                'section1': section1,
                                'section2': section2
                            })
                    except (ValueError, TypeError, Exception) as e:
                        # Silently skip problematic pairs
                        continue
            
            if cross_corrs:
                correlations[f"{section1} vs {section2}"] = cross_corrs
    
    if processed > 0:
        print()  # New line after progress indicator
    
    return correlations


def calculate_mutual_information(df, categorized, stats):
    """Calculate mutual information between sections with optimized computation."""
    mi_results = {}
    
    sections = list(categorized.keys())
    min_data_points = 10  # Minimum data points required for reliable MI
    min_mi_threshold = 0.001  # Minimum MI to report
    
    # Helper is shared with correlation calculation
    def _numeric_vars(section_name):
        """Helper to get numeric, non-ID variables for a section."""
        vars_list = stats[section_name].get("numeric_variables", [])
        clean = []
        for v in vars_list:
            if is_excluded_column(v):
                continue
            clean.append(v)
        return clean

    # Calculate total pairs for progress tracking
    total_pairs = sum(
        len(_numeric_vars(s1)) * len(_numeric_vars(s2))
        for i, s1 in enumerate(sections)
        for s2 in sections[i + 1 :]
    )
    processed = 0
    
    for i, section1 in enumerate(sections):
        for section2 in sections[i + 1 :]:
            vars1 = _numeric_vars(section1)
            vars2 = _numeric_vars(section2)
            
            if not vars1 or not vars2:
                continue
            
            # Calculate MI pairwise for each variable pair
            mi_pairs = []
            
            for v1 in vars1:
                if v1 not in df.columns:
                    continue
                # Double-check exclusion (defense in depth)
                if is_excluded_column(v1):
                    continue
                
                # Convert to numeric once per variable, handling duplicate names
                col1 = df[v1]
                if isinstance(col1, pd.DataFrame):
                    if col1.shape[1] == 0:
                        continue
                    col1 = col1.iloc[:, 0]
                data1 = pd.to_numeric(col1, errors='coerce')
                valid_count1 = data1.notna().sum()
                
                if valid_count1 < min_data_points:
                    continue
                
                for v2 in vars2:
                    if v2 not in df.columns or v1 == v2:
                        continue
                    # Double-check exclusion (defense in depth)
                    if is_excluded_column(v2):
                        continue
                    
                    processed += 1
                    if processed % 50 == 0:
                        print(f"   Processing MI: {processed}/{total_pairs} pairs...", end='\r')
                    
                    # Convert to numeric
                    col2 = df[v2]
                    if isinstance(col2, pd.DataFrame):
                        if col2.shape[1] == 0:
                            continue
                        col2 = col2.iloc[:, 0]
                    data2 = pd.to_numeric(col2, errors='coerce')
                    valid_count2 = data2.notna().sum()
                    
                    if valid_count2 < min_data_points:
                        continue
                    
                    try:
                        # Get data for this specific pair (need complete cases for MI)
                        pair_data = pd.DataFrame({v1: data1, v2: data2}).dropna()
                        
                        if len(pair_data) < min_data_points:
                            continue
                        
                        # Check for constant variables (MI would be 0)
                        if pair_data[v1].nunique() < 2 or pair_data[v2].nunique() < 2:
                            continue
                        
                        x = pair_data[v1].values.reshape(-1, 1)
                        y = pair_data[v2].values
                        
                        # Use regression for continuous variables
                        # Increase n_neighbors for better estimation with small datasets
                        n_neighbors = min(3, max(1, len(pair_data) // 10))
                        mi_val = mutual_info_regression(
                            x, y, 
                            random_state=42,
                            n_neighbors=n_neighbors
                        )[0]
                        
                        if mi_val > min_mi_threshold:
                            mi_pairs.append({
                                'var1': v1,
                                'var2': v2,
                                'mutual_information': float(mi_val),
                                'n_observations': len(pair_data),
                                'section1': section1,
                                'section2': section2
                            })
                    except (ValueError, TypeError, Exception) as e:
                        # Silently skip problematic pairs
                        continue
            
            if mi_pairs:
                mi_results[f"{section1} vs {section2}"] = mi_pairs
    
    if processed > 0:
        print()  # New line after progress indicator
    
    return mi_results


def calculate_section_aggregates(df, categorized, stats):
    """Calculate aggregate measures for each section with improved robustness."""
    aggregates = {}
    
    for section_name, columns in categorized.items():
        vars_list = stats[section_name].get('variables', [])
        
        if not vars_list:
            continue
        
        data = prepare_numeric_data(df, vars_list)
        
        if len(data) == 0 or len(data.columns) == 0:
            continue
        
        # Calculate section-level statistics (mean across variables per row)
        # Use fillna with median (more robust than mean) to handle missing values
        try:
            # Calculate per-row means, handling missing values
            # Only use rows with at least some data
            row_means = data.mean(axis=1, skipna=True)
            
            # Filter out rows with all NaN
            valid_rows = row_means.notna()
            
            if valid_rows.sum() < 5:
                continue
            
            section_means = row_means[valid_rows]
            
            aggregates[section_name] = {
                'mean': float(section_means.mean()),
                'std': float(section_means.std()) if len(section_means) > 1 else 0.0,
                'min': float(section_means.min()),
                'max': float(section_means.max()),
                'median': float(section_means.median()),
                'n_valid_rows': int(valid_rows.sum()),
                'total_rows': len(data)
            }
        except (ValueError, TypeError, Exception) as e:
            # Skip sections with calculation errors
            continue
    
    return aggregates


def find_top_relationships(correlations, mi_results, top_n=20):
    """Find top relationships by correlation and mutual information."""
    # Top correlations
    all_corrs = []
    for section_pair, pairs in correlations.items():
        for pair in pairs:
            all_corrs.append({
                'type': 'correlation',
                'section_pair': section_pair,
                'var1': pair['var1'],
                'var2': pair['var2'],
                'value': abs(pair['correlation']),
                'raw_value': pair['correlation']
            })
    
    # Top mutual information
    all_mi = []
    for section_pair, pairs in mi_results.items():
        for pair in pairs:
            all_mi.append({
                'type': 'mutual_information',
                'section_pair': section_pair,
                'var1': pair['var1'],
                'var2': pair['var2'],
                'value': pair['mutual_information'],
                'raw_value': pair['mutual_information']
            })
    
    top_corrs = sorted(all_corrs, key=lambda x: x['value'], reverse=True)[:top_n]
    top_mi = sorted(all_mi, key=lambda x: x['value'], reverse=True)[:top_n]
    
    return top_corrs, top_mi


def generate_report(stats, correlations, mi_results, aggregates, top_corrs, top_mi, output_file):
    """Generate analysis report."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("PROFILING SCHEMA AND RELATIONSHIP ANALYSIS\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Section Statistics
        f.write("=" * 80 + "\n")
        f.write("SECTION STATISTICS\n")
        f.write("=" * 80 + "\n\n")
        
        for section_name, section_stats in stats.items():
            f.write(f"Section: {section_name}\n")
            f.write(f"  Number of variables: {section_stats['num_variables']}\n")
            f.write(f"  Number of observations: {section_stats['num_observations']}\n")
            f.write(f"  Missing data: {section_stats['missing_percentage']:.2f}%\n")
            if section_stats['variables']:
                f.write(f"  Variables: {', '.join(section_stats['variables'][:5])}")
                if len(section_stats['variables']) > 5:
                    f.write(f" ... ({len(section_stats['variables'])} total)")
                f.write("\n")
            f.write("\n")
        
        # Section Aggregates
        f.write("=" * 80 + "\n")
        f.write("SECTION AGGREGATE STATISTICS\n")
        f.write("=" * 80 + "\n\n")
        
        for section_name, agg_stats in aggregates.items():
            f.write(f"Section: {section_name}\n")
            f.write(f"  Mean: {agg_stats['mean']:.4f}\n")
            f.write(f"  Std: {agg_stats['std']:.4f}\n")
            f.write(f"  Min: {agg_stats['min']:.4f}\n")
            f.write(f"  Max: {agg_stats['max']:.4f}\n")
            f.write(f"  Median: {agg_stats['median']:.4f}\n")
            f.write("\n")
        
        # Top Correlations
        f.write("=" * 80 + "\n")
        f.write("TOP CORRELATIONS BETWEEN SECTIONS\n")
        f.write("=" * 80 + "\n\n")
        
        for i, corr in enumerate(top_corrs, 1):
            f.write(f"{i}. {corr['var1']} <-> {corr['var2']}\n")
            f.write(f"   Sections: {corr['section_pair']}\n")
            f.write(f"   Correlation: {corr['raw_value']:.4f}\n")
            f.write("\n")
        
        # Top Mutual Information
        f.write("=" * 80 + "\n")
        f.write("TOP MUTUAL INFORMATION BETWEEN SECTIONS\n")
        f.write("=" * 80 + "\n\n")
        f.write("(Higher values indicate stronger non-linear relationships)\n\n")
        
        for i, mi in enumerate(top_mi, 1):
            f.write(f"{i}. {mi['var1']} <-> {mi['var2']}\n")
            f.write(f"   Sections: {mi['section_pair']}\n")
            f.write(f"   Mutual Information: {mi['raw_value']:.4f}\n")
            f.write("\n")
        
        # Cross-Section Correlation Summary
        f.write("=" * 80 + "\n")
        f.write("CROSS-SECTION CORRELATION SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        for section_pair, pairs in correlations.items():
            if pairs:
                corr_values = [abs(p['correlation']) for p in pairs]
                f.write(f"{section_pair}:\n")
                f.write(f"  Number of relationships: {len(pairs)}\n")
                f.write(f"  Mean |correlation|: {np.mean(corr_values):.4f}\n")
                f.write(f"  Max |correlation|: {np.max(corr_values):.4f}\n")
                f.write(f"  Strong relationships (|r| > 0.5): {sum(1 for c in corr_values if c > 0.5)}\n")
                f.write("\n")
        
        # Cross-Section MI Summary
        f.write("=" * 80 + "\n")
        f.write("CROSS-SECTION MUTUAL INFORMATION SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        for section_pair, pairs in mi_results.items():
            if pairs:
                mi_values = [p['mutual_information'] for p in pairs]
                f.write(f"{section_pair}:\n")
                f.write(f"  Number of relationships: {len(pairs)}\n")
                f.write(f"  Mean MI: {np.mean(mi_values):.4f}\n")
                f.write(f"  Max MI: {np.max(mi_values):.4f}\n")
                f.write(f"  Strong relationships (MI > 0.5): {sum(1 for m in mi_values if m > 0.5)}\n")
                f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")


def save_results_json(stats, correlations, mi_results, aggregates, top_corrs, top_mi, output_file):
    """Save results as JSON for further analysis."""
    results = {
        'metadata': {
            'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'analysis_type': 'Profiling Schema and Relationship Analysis'
        },
        'section_statistics': stats,
        'section_aggregates': aggregates,
        'correlations': correlations,
        'mutual_information': mi_results,
        'top_correlations': top_corrs,
        'top_mutual_information': top_mi
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)


def main():
    """Main analysis function."""
    print("=" * 80)
    print("PROFILING SCHEMA AND RELATIONSHIP ANALYSIS")
    print("=" * 80)
    print()
    
    # Load data
    print("1. Loading parameter dictionary...")
    param_dict = load_parameter_dictionary()
    print(f"   Loaded dictionary with {len(param_dict['sections'])} sections")
    
    print("\n2. Loading health data...")
    df, section_headers, column_names = load_health_data()
    print(f"   Loaded {len(df)} rows, {len(df.columns)} columns")
    
    # Categorize columns
    print("\n3. Categorizing columns by sections...")
    categorized = categorize_columns(df, param_dict)
    for section, cols in categorized.items():
        print(f"   {section}: {len(cols)} variables")
    
    # Calculate statistics
    print("\n4. Calculating section statistics...")
    stats = calculate_section_statistics(df, categorized)
    
    # Calculate aggregates
    print("\n5. Calculating section aggregates...")
    aggregates = calculate_section_aggregates(df, categorized, stats)
    
    # Calculate correlations
    print("\n6. Calculating cross-section correlations...")
    correlations = calculate_cross_section_correlations(df, categorized, stats)
    total_corrs = sum(len(pairs) for pairs in correlations.values())
    print(f"   Found {total_corrs} correlation pairs")
    if total_corrs == 0:
        print("   Debug: Checking why no correlations found...")
        # Quick test
        test_vars = ['Longevity Score', 'Vo2Max']
        if all(v in df.columns for v in test_vars):
            test_data = df[test_vars].copy()
            test_data[test_vars[0]] = pd.to_numeric(test_data[test_vars[0]], errors='coerce')
            test_data[test_vars[1]] = pd.to_numeric(test_data[test_vars[1]], errors='coerce')
            test_corr = test_data[test_vars[0]].corr(test_data[test_vars[1]])
            print(f"   Test correlation ({test_vars[0]} vs {test_vars[1]}): {test_corr:.4f}")
    
    # Calculate mutual information
    print("\n7. Calculating mutual information...")
    mi_results = calculate_mutual_information(df, categorized, stats)
    print(f"   Found {sum(len(pairs) for pairs in mi_results.values())} MI pairs")
    
    # Find top relationships
    print("\n8. Identifying top relationships...")
    top_corrs, top_mi = find_top_relationships(correlations, mi_results, top_n=20)
    print(f"   Top {len(top_corrs)} correlations identified")
    print(f"   Top {len(top_mi)} mutual information relationships identified")
    
    # Generate reports
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    report_file = os.path.join(output_dir, f"schema_relationship_analysis_{timestamp}.txt")
    json_file = os.path.join(output_dir, f"schema_relationship_analysis_{timestamp}.json")
    
    print(f"\n9. Generating reports...")
    generate_report(stats, correlations, mi_results, aggregates, top_corrs, top_mi, report_file)
    save_results_json(stats, correlations, mi_results, aggregates, top_corrs, top_mi, json_file)
    
    print(f"\n✓ Analysis complete!")
    print(f"  Text report: {report_file}")
    print(f"  JSON results: {json_file}")
    
    return report_file, json_file


if __name__ == "__main__":
    main()

