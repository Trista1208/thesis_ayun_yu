"""
Create parameter dictionary for the health dataset.
Extracts column names from Excel and matches them with information from the PDF report.
"""

import os
import sys
import json
import re
from datetime import datetime

try:
    import pandas as pd
    # openpyxl is required by pandas for Excel reading
    import openpyxl  # noqa: F401
except (ImportError, ValueError) as e:
    error_msg = str(e)
    print("=" * 70)
    print("ERROR: Cannot import required packages!")
    print("=" * 70)
    print(f"Error: {error_msg}")

    # Check for specific binary incompatibility error
    if "numpy.dtype size changed" in error_msg or "binary incompatibility" in error_msg:
        print("\n" + "-" * 70)
        print("BINARY INCOMPATIBILITY DETECTED")
        print("-" * 70)
        print("This error indicates that pandas/numpy were compiled against")
        print("a different version of numpy than what's currently installed.")
        print("This often happens when using system Python instead of a")
        print("virtual environment.")

    # Get script directory for better path display
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("\n" + "-" * 70)
    print("SOLUTIONS:")
    print("-" * 70)
    print("\n1. Use the virtual environment (RECOMMENDED):")
    print(f"   cd {script_dir}")
    print("   source venv/bin/activate")
    print("   python create_parameter_dictionary.py")
    print("\n2. Use venv Python directly (no activation needed):")
    print(f"   cd {script_dir}")
    print("   venv/bin/python create_parameter_dictionary.py")
    print("\n3. If using system Python, you may need to reinstall:")
    print("   pip install --upgrade numpy pandas openpyxl")
    print("   (Warning: This may affect other projects)")

    sys.exit(1)
except Exception as e:
    error_msg = str(e)
    error_type = type(e).__name__
    print("=" * 70)
    print("ERROR: Unexpected error importing packages!")
    print("=" * 70)
    print(f"Error type: {error_type}")
    print(f"Error message: {error_msg}")

    # Get script directory for better path display
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("\n" + "-" * 70)
    print("RECOMMENDED SOLUTIONS:")
    print("-" * 70)
    print("\n1. Use the virtual environment (RECOMMENDED):")
    print(f"   cd {script_dir}")
    print("   source venv/bin/activate")
    print("   python create_parameter_dictionary.py")
    print("\n2. Use venv Python directly (no activation needed):")
    print(f"   cd {script_dir}")
    print("   venv/bin/python create_parameter_dictionary.py")

    sys.exit(1)


def load_column_names():
    """Load all column names from the Excel file."""
    file_path = "health_export_29.10.2025 10_19.xlsx"
    
    # Read with multi-level headers to get pandas-processed column names (with .1, .2 suffixes)
    df_multi = pd.read_excel(file_path, header=[0, 1])
    
    # Extract section headers and column names from multi-index
    section_headers = []
    actual_column_names = []
    
    for col_tuple in df_multi.columns:
        section_headers.append(col_tuple[0])
        actual_column_names.append(col_tuple[1])
    
    # Forward-fill section headers (for merged cells in Excel)
    last_valid_section = None
    for i in range(len(section_headers)):
        if pd.notna(section_headers[i]) and str(section_headers[i]).strip():
            last_valid_section = str(section_headers[i]).strip()
            section_headers[i] = last_valid_section
        elif last_valid_section:
            section_headers[i] = last_valid_section
    
    return section_headers, actual_column_names


def extract_pdf_parameters():
    """
    Extract all parameter information from the PDF text.
    Returns a dictionary with parameter details extracted from the PDF.
    """
    pdf_text_file = "005bd16b-bceb-4149-8be3-87a2a60520e3.txt"
    
    if not os.path.exists(pdf_text_file):
        print(f"Warning: PDF text file not found: {pdf_text_file}")
        return {}
    
    with open(pdf_text_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pdf_parameters = {}
    
    # Define parameter extraction patterns
    # Format: (param_name, pattern_to_find_parameter_block)
    parameter_patterns = [
        # Body Composition
        ('Bone Mineral Density', r'Bone Mineral Density.*?(?=Resting Metabolic Rate|Appendicular|$)'),
        ('Resting Metabolic Rate', r'Resting Metabolic Rate.*?(?=Appendicular|$)'),
        ('Appendicular Lean Mass Index', r'Appendicular Lean Mass Index\nin\s+kg/m2\n[\d\.\s]+\nDescription\n(.*?)(?=\nYour data explained|\nLean Mass Index\n)'),
        ('Lean Mass Index', r'^Lean Mass Index\nin\s+kg/m2\n[\d\.\s]+\nDescription\n(.*?)(?=\nYour data explained|\nVisceral|$)'),
        ('Visceral Adipose Tissue', r'Visceral Adipose Tissue.*?(?=Body Fat|$)'),
        ('Body Fat Percentage', r'Body Fat Percentage.*?(?=Fat Mass|$)'),
        ('Fat Mass Index', r'Fat Mass Index.*?(?=Trunk|$)'),
        ('Trunk Lean Mass', r'Trunk Lean Mass.*?(?=Arms|$)'),
        ('Arms Lean Mass', r'Arms Lean Mass.*?(?=Legs|$)'),
        ('Legs Lean Mass', r'Legs Lean Mass.*?(?=Physical Performance|Bloodwork|$)'),
        
        # Bloodwork
        ('RDW', r'RDW\s+in\s+.*?(?=Homocystein|$)'),
        ('Homocystein', r'Homocystein\nin\s+µmol/l\n[\d\.\s]+\nDescription\n(.*?)(?=\nYour data explained|\nFibrinogen|$)'),
        ('Fibrinogen', r'Fibrinogen\s+in\s+.*?(?=hsCRP|$)'),
        ('hsCRP', r'hsCRP\s+in\s+.*?(?=ASAT|$)'),
        ('ASAT', r'ASAT\s+in\s+.*?(?=ALAT|$)'),
        ('ALAT', r'ALAT\s+in\s+.*?(?=GGT|$)'),
        ('GGT', r'GGT\s+in\s+.*?(?=Bilirubin|$)'),
        ('Bilirubin', r'Bilirubin\s+in\s+.*?(?=HbA1c|$)'),
        ('HbA1c', r'HbA1c\s+in\s+.*?(?=Glucose fasted|$)'),
        ('Glucose fasted', r'Glucose fasted\s+in\s+.*?(?=Uric acid|$)'),
        ('Uric acid', r'Uric acid\s+in\s+.*?(?=Urea|$)'),
        ('Urea', r'Urea\s+in\s+.*?(?=Cystatin C|$)'),
        ('Cystatin C', r'Cystatin C\nin\s+mg/L\n[\d\.\s]+\nDescription\n(.*?)(?=\nYour data explained|\nK\s+in|$)'),
        ('K', r'K\s+in\s+.*?(?=Na\s+in|$)'),
        ('Na', r'Na\s+in\s+.*?(?=Ca\s+in|$)'),
        ('Ca', r'Ca\s+in\s+.*?(?=Phosphate|$)'),
        ('Phosphate', r'Phosphate\s+in\s+.*?(?=Iron|$)'),
        ('Iron', r'Iron\s+in\s+.*?(?=Transferrin\s+[^S]|Transferrin Saturation|$)'),
        ('Transferrin', r'Transferrin\s+(?!Saturation).*?(?=Transferrin Saturation|$)'),
        ('Transferrin Saturation', r'Transferrin Saturation\s+in\s+.*?(?=Ferritin|$)'),
        ('Ferritin', r'Ferritin\s+in\s+.*?(?=HDL|$)'),
        ('HDL', r'HDL\s+in\s+.*?(?=LDL|$)'),
        ('LDL', r'LDL\s+in\s+.*?(?=Triglyceride|$)'),
        ('Triglyceride', r'Triglyceride\s+in\s+.*?(?=ApoB|$)'),
        ('ApoB', r'ApoB\s+in\s+.*?(?=LP\(a\)|Lp\(a\)|Omega|$)'),
        ('LP(a)', r'LP\(a\)|Lp\(a\).*?(?=Omega-3|$)'),
        # Note: Omega-3 Index is handled separately below with a specific pattern
        ('Protein', r'Protein\s+in\s+.*?(?=Mg Serum|$)'),
        ('Mg Serum', r'Mg Serum\s+in\s+.*?(?=Selenium|$)'),
        ('Selenium', r'Selenium\s+in\s+.*?(?=Vitamin D|$)'),
        ('Vit D', r'Vitamin D\nin\s+µg/l\n[\d\.\s]+\nDescription\n(.*?)(?=\nYour data explained|\nVitamin B12|$)'),
        ('Vit B12', r'Vitamin B12\s+in\s+.*?(?=Folic acid|$)'),
        ('Folic acid', r'Folic acid\s+in\s+.*?(?=TSH|$)'),
        ('TSH', r'TSH\s+in\s+.*?(?=fT3|$)'),
        ('fT3', r'fT3\s+in\s+.*?(?=Insulin\s+in|$)'),
        ('Fasting insulin', r'Insulin\s+in\s+.*?(?=HOMA-Index|$)'),
        ('HOMA Index', r'HOMA-Index.*?(?=SHBG|$)'),
        ('SHBG', r'SHBG\s+in\s+.*?(?=Testosteron\s+[^F]|Free Testosteron|$)'),
        ('Tesosterone', r'Testosteron\s+(?!Free).*?(?=Free Testosteron|$)'),
        ('Free Testosteron', r'Free Testosteron\s+in\s+.*?(?=DHEA-Sulfate|$)'),
        ('DHEA-Sulfate', r'DHEA-Sulfate\s+in\s+.*?(?=Pregnenolone|$)'),
        ('Pregnenolone', r'Pregnenolone\s+in\s+.*?(?=Genetics|$)'),
        
        # Physical Performance
        ('VO2max', r'VO2max\s+in\s+.*?(?=HR max|$)'),
        ('HR max', r'HR max\s+.*?(?=Heart Rate at Fatmax|$)'),
        ('Heart Rate at Fatmax', r'Heart Rate at Fatmax\s+.*?(?=Heart Rate at VT1|$)'),
        ('HR at VT1', r'Heart Rate at VT1\s+.*?(?=Heart Rate at VT2|$)'),
        ('HR at VT2', r'Heart Rate at VT2\s+.*?(?=CMJ|$)'),
        ('Counter movement jump', r'CMJ\s+in\s+.*?(?=Y Balance|$)'),
        ('Y-Balance Composite Score', r'Y Balance Total\s+in\s+.*?(?=30 sec|$)'),
        
        # HRV (Heart Rate Variability)
        ('HRV Gesamt score', r'Overall Score\s+in\s+points\s+from\s+0\s+to\s+100\s+[\d\.\s]+\s*Description\s+(.*?)(?=\nYour data explained|\nStress\s+&\s+Recovery|\nSleep\s+in\s+points|\nPhysical Activity\s+in\s+points|$)'),
        ('HRV Stress score', r'Stress\s+&\s+Recovery\s+in\s+points\s+from\s+0\s+to\s+100\s+[\d\.\s]+\s*Description\s+(.*?)(?=\nYour data explained|\nSleep\s+in\s+points|\nPhysical Activity\s+in\s+points|$)'),
        ('HRV Sleep score', r'Sleep\s+in\s+points\s+from\s+0\s+to\s+100\s+[\d\.\s]+\s*Description\s+(.*?)(?=\nYour data explained|\nPhysical Activity\s+in\s+points|$)'),
        ('HRV physical activity score', r'Physical Activity\s+in\s+points\s+from\s+0\s+to\s+100\s+[\d\.\s]+\s*Description\s+(.*?)(?=\nYour data explained|---|$)'),
        
        # Special cases that need specific patterns
        ('Omega-3 Index', r'Omega-3 Index\n([\d\.\s]+)\nDescription\n(.*?)(?=\nYour data explained|\n[A-Z][a-z]+\s+(?:in\s|Description)|---\s+Page|\Z)'),
        ('Protein', r'Protein\nin\s+g/l\n[\d\.\s]+\nDescription\n(.*?)(?=\nYour data explained|\nMg Serum|$)'),
    ]
    
    # Extract general HRV description (applies to all HRV parameters)
    hrv_general_match = re.search(
        r'Analysis of the heart rate variability \(HRV\)\s+The short-.*?system \(ANS\) to adapt to stress and environmental changes\.',
        content, re.IGNORECASE | re.DOTALL
    )
    if hrv_general_match:
        hrv_general_desc = "The short- and long-term assessment of HRV provides insights into the ability of the autonomic nervous system (ANS) to adapt to stress and environmental changes."
        # Store for later use
        pdf_parameters['_HRV_GENERAL_DESCRIPTION'] = hrv_general_desc
    
    # Extract each parameter
    for param_name, pattern in parameter_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            # For HRV parameters, extract description directly from match
            if param_name.startswith('HRV'):
                # HRV patterns capture description directly
                description = match.group(1).strip() if match.groups() else match.group(0)
                # Clean up description - remove line breaks and normalize whitespace
                description = description.replace('\n', ' ')
                description = re.sub(r'\s+', ' ', description)
                description = description.strip()
                # Remove page number artifacts
                description = re.sub(r'^\d+\s*---\s*Page\s+\d+\s*---\s*\d+\s*', '', description)
                description = re.sub(r'\s*---\s*Page\s+\d+\s*---\s*\d+\s*', '', description)
                # Remove any trailing incomplete sentences (cut off at word boundaries)
                description = re.sub(r'\s+[a-z]+\s*$', '', description)  # Remove trailing incomplete words
                
                # Create param_info with description
                param_info = {'description': description, 'unit': 'points'}
                
                # Extract reference ranges from the block
                block = match.group(0)
                range_match = re.search(r'(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)', block)
                if range_match:
                    ranges = [float(x) for x in range_match.groups()]
                    param_info['reference_ranges'] = sorted(ranges)
                
                # Add general HRV description if available
                if '_HRV_GENERAL_DESCRIPTION' in pdf_parameters:
                    general_desc = pdf_parameters['_HRV_GENERAL_DESCRIPTION']
                    param_info['description'] = f"{general_desc} {description}"
                
                pdf_parameters[param_name] = param_info
            elif param_name == 'Omega-3 Index':
                # Omega-3 Index pattern: Omega-3 Index\n(ranges)\nDescription\n(description)
                # match.group(1) = ranges, match.group(2) = description
                ranges_str = match.group(1).strip() if len(match.groups()) >= 1 and match.group(1) else None
                description = match.group(2).strip() if len(match.groups()) >= 2 and match.group(2) else None
                
                if description:
                    # Clean up description
                    description = description.replace('\n', ' ')
                    description = re.sub(r'\s+', ' ', description)
                    description = description.strip()
                    # Remove page number artifacts
                    description = re.sub(r'\s*---\s*Page\s+\d+\s*---\s*\d+\s*', '', description)
                    # Remove trailing numbers
                    description = re.sub(r'\s+\d+\.?\d*\s*$', '', description)
                    # Remove HRV description if accidentally included
                    description = re.sub(r'^The short-.*?environmental changes\.\s*', '', description, flags=re.DOTALL)
                
                if description and len(description) > 20:
                    param_info = {'description': description}
                    
                    # Extract reference ranges
                    if ranges_str:
                        try:
                            ranges = [float(x) for x in ranges_str.split() if x.strip()]
                            if len(ranges) >= 2:
                                param_info['reference_ranges'] = sorted(ranges)
                        except (ValueError, AttributeError):
                            pass
                    
                    pdf_parameters[param_name] = param_info
            elif param_name in ['Appendicular Lean Mass Index', 'Lean Mass Index', 'Homocystein', 'Cystatin C', 'Vit D', 'Protein']:
                # These have specific patterns that capture description directly
                description = match.group(1).strip() if match.groups() else None
                if description:
                    # Clean up description
                    description = description.replace('\n', ' ')
                    description = re.sub(r'\s+', ' ', description)
                    description = description.strip()
                    # Remove page number artifacts
                    description = re.sub(r'\s*---\s*Page\s+\d+\s*---\s*\d+\s*', '', description)
                    # Remove trailing numbers
                    description = re.sub(r'\s+\d+\.?\d*\s*$', '', description)
                    # Remove HRV description if accidentally included
                    description = re.sub(r'^The short-.*?environmental changes\.\s*', '', description, flags=re.DOTALL)
                    
                    if description and len(description) > 20:
                        param_info = {'description': description}
                        # Extract unit and ranges from the full block
                        block = match.group(0)
                        # Fix specific units
                        if param_name == 'Homocystein':
                            param_info['unit'] = 'µmol/l'
                        elif param_name == 'Cystatin C':
                            param_info['unit'] = 'mg/L'
                        elif param_name == 'Vit D':
                            # Vitamin D (25-hydroxyvitamin D) is typically reported in nmol/L by most labs
                            # Conversion: 1 ng/mL = 2.5 nmol/L
                            # 33.0 µg/L = 33.0 ng/mL = 82.5 nmol/L (optimal >75 nmol/L or >30 ng/mL)
                            param_info['unit'] = 'nmol/L'
                            # Add note about unit conversion
                            param_info['unit_note'] = '25-hydroxyvitamin D is reported in nmol/L. Conversion: 1 ng/mL = 2.5 nmol/L. Optimal: >75 nmol/L (>30 ng/mL).'
                            # Convert reference ranges from ng/mL to nmol/L if they exist
                            # Typical ranges: 30 ng/mL = 75 nmol/L, 60 ng/mL = 150 nmol/L, 100 ng/mL = 250 nmol/L
                            if 'reference_ranges' in param_info and param_info['reference_ranges']:
                                param_info['reference_ranges'] = [r * 2.5 for r in param_info['reference_ranges']]
                        elif param_name in ['Appendicular Lean Mass Index', 'Lean Mass Index']:
                            param_info['unit'] = 'kg/m²'
                        elif param_name == 'Fat Mass Index':
                            param_info['unit'] = 'kg/m²'
                        elif param_name == 'Bone Mineral Density':
                            param_info['unit'] = 'g/cm²'  # Standard unit for BMD
                        elif param_name == 'Protein':
                            param_info['unit'] = 'g/l'
                        else:
                            unit_match = re.search(r'in\s+([a-zA-Z/%²³µ·\-]+(?:\s*/\s*[a-zA-Z/%²³µ·\-]+)*)', block, re.IGNORECASE)
                            if unit_match:
                                unit = unit_match.group(1).strip()
                                # Normalize kg/m2 to kg/m²
                                if unit == 'kg/m2':
                                    unit = 'kg/m²'
                                elif unit == 'g/cm2':
                                    unit = 'g/cm²'
                                elif unit == 'g/cm3':
                                    unit = 'g/cm³'
                                if len(unit) <= 15 and len(unit) > 1 and unit.lower() not in ['in', 'c', 'd']:
                                    param_info['unit'] = unit
                        
                        # Extract reference ranges
                        range_match = re.search(r'(\d+\.?\d*)\s+(\d+\.?\d*)(?:\s+(\d+\.?\d*))?(?:\s+(\d+\.?\d*))?', block)
                        if range_match:
                            ranges = [float(x) for x in range_match.groups() if x]
                            if len(ranges) >= 2:
                                param_info['reference_ranges'] = sorted(ranges)
                        
                        # Special handling for specific parameters
                        if param_name == 'hsCRP':
                            # Update ranges to reflect: <0.8-1.0 optimal, <1.0 low risk, 1.0-3.0 average risk
                            # Keep extracted ranges but add interpretation note
                            param_info['reference_range_note'] = '<0.8-1.0 mg/L optimal, <1.0 mg/L low risk, 1.0-3.0 mg/L average risk, >3.0 mg/L high risk'
                        elif param_name == 'Vit D':
                            # Convert reference ranges from ng/mL to nmol/L (multiply by 2.5)
                            # Typical ranges: 30 ng/mL = 75 nmol/L, 60 ng/mL = 150 nmol/L, 100 ng/mL = 250 nmol/L
                            if 'reference_ranges' in param_info and param_info['reference_ranges']:
                                # Check if ranges are in ng/mL (values < 100) and convert to nmol/L
                                if param_info['reference_ranges'][0] < 100:
                                    param_info['reference_ranges'] = [r * 2.5 for r in param_info['reference_ranges']]
                        
                        pdf_parameters[param_name] = param_info
            else:
                # For other parameters, use standard extraction
                block = match.group(0)
                param_info = extract_parameter_info(param_name, block)
                if param_info:
                    # Add special notes for specific parameters
                    if param_name == 'HOMA Index':
                        # Add note about unit systems
                        if 'description' in param_info:
                            param_info['description'] += ' Note: HOMA-IR calculation uses different constants for US units (÷405) vs SI units (÷22.5). Ensure the correct unit system is used for glucose (mg/dL vs mmol/L) and insulin (µU/mL vs pmol/L) when calculating or interpreting HOMA values.'
                    elif param_name == 'HbA1c':
                        # Add note about AYUN's recommendation for optimal metabolic health
                        if 'description' in param_info:
                            param_info['description'] += ' Note: While <5.7% is officially normal, AYUN often recommends <5.4% for optimal metabolic health, as many longevity-focused clinics flag ≥5.4% as an early insulin resistance warning.'
                    elif param_name == 'hsCRP':
                        # Add reference range interpretation note
                        param_info['reference_range_note'] = '<0.8-1.0 mg/L optimal, <1.0 mg/L low risk, 1.0-3.0 mg/L average risk, >3.0 mg/L high risk'
                    pdf_parameters[param_name] = param_info
    
    # Remove temporary HRV general description
    pdf_parameters.pop('_HRV_GENERAL_DESCRIPTION', None)
    
    # GENERAL EXTRACTION: Find all parameters with descriptions using a general pattern
    # This catches parameters that weren't in the hardcoded list above
    # Pattern: Parameter name (capitalized, on its own line) -> optional unit -> optional ranges -> Description -> description text
    # Also handle cases with "Your" prefix (e.g., "Your Longevity Score")
    general_param_pattern = re.compile(
        r'^(?:Your\s+)?([A-Z][a-zA-Z\s\(\)\-\/]+?)\n'  # Parameter name (optionally prefixed with "Your")
        r'(?:Your\s+[A-Z][a-zA-Z\s\(\)\-\/]+?\n)?'  # Skip duplicate "Your X" lines
        r'(?:Description\n)?'  # Optional duplicate "Description" line
        r'Description\n'  # "Description" header
        r'(.*?)(?=\nYour data explained|\n[A-Z][a-z]+\s+(?:in\s|Description)|---\s+Page|\Z)',  # Description text
        re.MULTILINE | re.DOTALL
    )
    
    # Also handle parameters with unit and ranges before Description
    # This pattern handles: Parameter name -> ranges (no unit) -> Description
    general_param_pattern_with_ranges = re.compile(
        r'^([A-Z][a-zA-Z\s\(\)\-\/]+?)\n'  # Parameter name (can include hyphens like "Omega-3 Index")
        r'(?:([\d\.\s]+)\n)?'  # Optional reference ranges (numbers, no "in" prefix)
        r'Description\n'  # "Description" header
        r'(.*?)(?=\nYour data explained|\n[A-Z][a-z]+\s+(?:in\s|Description)|---\s+Page|\Z)',  # Description text
        re.MULTILINE | re.DOTALL
    )
    
    # Pattern with unit: Parameter name -> unit -> ranges -> Description
    general_param_pattern_with_unit = re.compile(
        r'^([A-Z][a-zA-Z\s\(\)\-\/]+?)\n'  # Parameter name
        r'in\s+([^\n]+?)\n'  # Unit line "in [unit]"
        r'(?:([\d\.\s]+)\n)?'  # Optional reference ranges (numbers)
        r'Description\n'  # "Description" header
        r'(.*?)(?=\nYour data explained|\n[A-Z][a-z]+\s+(?:in\s|Description)|---\s+Page|\Z)',  # Description text
        re.MULTILINE | re.DOTALL
    )
    
    # Find all matches with all patterns
    all_matches = []
    for match in general_param_pattern.finditer(content):
        param_name = match.group(1).strip()
        description = match.group(2).strip() if match.group(2) else None
        all_matches.append((param_name, None, None, description))
    
    for match in general_param_pattern_with_ranges.finditer(content):
        param_name = match.group(1).strip()
        ranges_str = match.group(2).strip() if match.group(2) else None
        description = match.group(3).strip() if match.group(3) else None
        all_matches.append((param_name, None, ranges_str, description))
    
    for match in general_param_pattern_with_unit.finditer(content):
        param_name = match.group(1).strip()
        unit = match.group(2).strip() if match.group(2) else None
        ranges_str = match.group(3).strip() if match.group(3) else None
        description = match.group(4).strip() if match.group(4) else None
        all_matches.append((param_name, unit, ranges_str, description))
    
    # Process all matches
    for param_name, unit, ranges_str, description in all_matches:
        # Skip if we already have this parameter (from hardcoded patterns)
        if param_name in pdf_parameters:
            continue
        
        # Skip very short names (likely not parameters)
        if len(param_name) < 3:
            continue
        
        # Skip common non-parameter words (but allow "Your X" patterns)
        skip_words = ['Page', 'Description', 'Designation', 'Value', 'Table', 'Contents', 'Check']
        if any(param_name == word or (len(param_name) > len(word) and param_name.startswith(word + ' ')) for word in skip_words):
            continue
        
        # Normalize parameter name (remove "Your" prefix for matching)
        normalized_name = param_name.replace('Your ', '').strip()
        
        # Clean up description
        if description:
            description = re.sub(r'\s+', ' ', description)
            description = description.replace('\n', ' ').strip()
            # Remove page number artifacts
            description = re.sub(r'\s*---\s*Page\s+\d+\s*---\s*\d+\s*', '', description)
            # Remove trailing numbers that might be values
            description = re.sub(r'\s+\d+\.?\d*\s*$', '', description)
            # Remove trailing text artifacts like "Dein Score", "Punkten", etc.
            description = re.sub(r'\s+(Dein Score|Punkten von 0 bis 100|Grad).*$', '', description, flags=re.IGNORECASE)
        
        # Extract reference ranges
        reference_ranges = None
        if ranges_str:
            try:
                ranges = [float(x) for x in ranges_str.split() if x.strip()]
                if len(ranges) >= 2:
                    reference_ranges = sorted(ranges)
            except (ValueError, AttributeError):
                pass
        
        # Clean up unit
        if unit:
            unit = unit.strip()
            # Limit unit length
            if len(unit) > 20:
                unit = None
        
        # Only add if we have a description
        if description and len(description) > 20:  # Minimum description length
            # Skip if this parameter already exists (from hardcoded patterns)
            if param_name in pdf_parameters:
                continue
            
            param_info = {'description': description}
            if unit and len(unit) <= 20:
                param_info['unit'] = unit
            if reference_ranges:
                param_info['reference_ranges'] = reference_ranges
            
            # NEVER add HRV general description to non-HRV parameters
            # Only HRV parameters should get the HRV general description
            # Also remove any HRV description that might have been accidentally included
            if param_name.startswith('HRV') and '_HRV_GENERAL_DESCRIPTION' in pdf_parameters:
                general_desc = pdf_parameters['_HRV_GENERAL_DESCRIPTION']
                # Remove HRV description if already present to avoid duplication
                description = re.sub(r'^The short-.*?environmental changes\.\s*', '', description, flags=re.DOTALL)
                param_info['description'] = f"{general_desc} {description}"
            else:
                # For non-HRV parameters, remove any HRV description that might have been included
                if 'description' in param_info:
                    param_info['description'] = re.sub(
                        r'^The short-.*?environmental changes\.\s*',
                        '',
                        param_info['description'],
                        flags=re.DOTALL
                    ).strip()
            
            pdf_parameters[param_name] = param_info
            if normalized_name != param_name and normalized_name not in pdf_parameters:
                pdf_parameters[normalized_name] = param_info
    
    return pdf_parameters


def extract_parameter_info(param_name, text_block):
    """
    Extract information from a parameter text block.
    Returns a dictionary with description, unit, reference_ranges, and interpretation.
    """
    info = {}
    
    # Extract unit - only look before "Description" to avoid matching description text
    # Split text block at "Description" to isolate the header section
    header_section = text_block.split('Description')[0] if 'Description' in text_block else text_block
    
    # Pattern: "in " followed by unit (typically short: kg, %, ml/min/kg, µmol/l, etc.)
    # Only match if it's a short unit (not a long phrase)
    # Match units like: kg, %, ml/min/kg, µmol/l, mg/L, µg/l, kg/m², kg/m2, etc.
    # Also handle single character units like "%"
    unit_match = re.search(r'in\s+([%a-zA-Z/²³µ·\-0-9]+(?:\s*/\s*[%a-zA-Z/²³µ·\-0-9]+)*)', header_section, re.IGNORECASE)
    if unit_match:
        unit = unit_match.group(1).strip()
        # Clean up unit - remove extra spaces
        unit = re.sub(r'\s+', ' ', unit)
        # Normalize common unit formats (kg/m2 -> kg/m², g/cm2 -> g/cm², etc.)
        if unit == 'kg/m2' or unit.lower() == 'kg/m2':
            unit = 'kg/m²'
        elif unit == 'g/cm2' or unit.lower() == 'g/cm2':
            unit = 'g/cm²'
        elif unit == 'g/cm3' or unit.lower() == 'g/cm3':
            unit = 'g/cm³'
        # Units are typically short (max ~15 chars for complex ones like "ml/min/kg")
        # Reject single letters that are likely not units (like "C", "D", "in")
        # But allow "%" as a valid single-character unit
        if len(unit) <= 15 and (len(unit) > 1 or unit == '%') and unit.lower() not in ['in', 'c', 'd']:
            info['unit'] = unit
        else:
            # If too long or invalid, it's probably not a unit
            info['unit'] = 'Unknown'
    else:
        # Try alternative patterns like "Average g/cm2"
        alt_unit_match = re.search(r'(Average)\s+([a-zA-Z/%²³µ·\-0-9]+(?:\s*/\s*[a-zA-Z/%²³µ·\-0-9]+)*)', header_section, re.IGNORECASE)
        if alt_unit_match:
            unit = alt_unit_match.group(2).strip()
            # Normalize common unit formats
            if unit == 'g/cm2' or unit.lower() == 'g/cm2':
                unit = 'g/cm²'
            elif unit == 'kg/m2' or unit.lower() == 'kg/m2':
                unit = 'kg/m²'
            elif unit == 'g/cm3' or unit.lower() == 'g/cm3':
                unit = 'g/cm³'
            info['unit'] = unit
        else:
            # Special cases: parameters that don't have explicit units in the text
            # but we know what they should be
            special_units = {
                'HR at VT1': 'bpm',
                'HR at VT2': 'bpm',
                'Heart Rate at VT1': 'bpm',
                'Heart Rate at VT2': 'bpm',
                'Heart Rate at Fatmax': 'bpm',
                'HR max': 'bpm',
                'Resting Metabolic Rate': 'kcal/day',
                'Fat Mass Index': 'kg/m²',
                'Bone Mineral Density': 'g/cm²',
                'Bone mineral density': 'g/cm²',  # Handle lowercase variant
                'Lean Mass Index': 'kg/m²',
                'Appendicular Lean Mass Index': 'kg/m²',
                'HbA1c': '%',
                'RDW': '%',
                'HbA1C': '%',  # Handle case variations
            }
            if param_name in special_units:
                info['unit'] = special_units[param_name]
            else:
                info['unit'] = 'Unknown'
    
    # Extract reference ranges (numbers on a scale, typically 2-4 numbers)
    # Look for patterns like "7.79 8.38 9.11 9.83" or "13.6 15.1"
    # But exclude single numbers that might be values, not ranges
    range_patterns = [
        r'(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)',  # 4 numbers
        r'(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)',  # 3 numbers
        r'(\d+\.?\d*)\s+(\d+\.?\d*)',  # 2 numbers
    ]
    
    reference_ranges = None
    for pattern in range_patterns:
        range_match = re.search(pattern, text_block)
        if range_match:
            try:
                ranges = [float(x) for x in range_match.groups()]
                # Validate and sort ranges to ensure ascending order
                if len(ranges) >= 2:
                    ranges_sorted = sorted(ranges)
                    # Only use if values make sense (not all the same, reasonable spread)
                    if ranges_sorted[0] < ranges_sorted[-1]:
                        reference_ranges = ranges_sorted
                        break
            except (ValueError, IndexError):
                continue
    
    if reference_ranges:
        info['reference_ranges'] = reference_ranges
    
    # Extract description (text after "Description")
    desc_match = re.search(r'Description\s+(.*?)(?=Your data explained|$)', text_block, re.DOTALL | re.IGNORECASE)
    if desc_match:
        description = desc_match.group(1).strip()
        # Clean up description
        description = re.sub(r'\s+', ' ', description)
        description = description.replace('\n', ' ').strip()
        # Remove page number artifacts (e.g., "--- Page 46 --- 46")
        description = re.sub(r'\s*---\s*Page\s+\d+\s*---\s*\d+\s*$', '', description)
        # Remove any trailing numbers that might be values (but keep ranges)
        description = re.sub(r'\s+\d+\.?\d*\s+\d+\.?\d*\s*$', '', description)  # Remove pairs of numbers
        description = re.sub(r'\s+\d+\.?\d*\s*$', '', description)  # Remove single trailing numbers
        info['description'] = description
    else:
        info['description'] = 'No description available'
    
    # Extract interpretation (text after "Your data explained")
    # Skip patient-specific interpretations - they're not useful for a general dictionary
    # Only include general interpretation guides if they exist
    # Standardize field name to 'interpretation' (not 'interpretation_guide')
    interp_match = re.search(r'Your data explained\s+(.*?)(?=Borderline|Your [A-Z]|$)', text_block, re.DOTALL | re.IGNORECASE)
    if interp_match:
        interpretation = interp_match.group(1).strip()
        # Clean up interpretation
        interpretation = re.sub(r'\s+', ' ', interpretation)
        interpretation = interpretation.replace('\n', ' ').strip()
        
        # Filter out patient-specific interpretations (those starting with "You", "Your", etc.)
        # These are not useful for a general parameter dictionary
        if interpretation and not re.match(r'^(You|Your|This|These)', interpretation, re.IGNORECASE):
            # Only include if it's a general interpretation guide
            if len(interpretation) > 500:
                interpretation = interpretation[:500] + "..."
            info['interpretation'] = interpretation  # Always use 'interpretation', not 'interpretation_guide'
        # Skip patient-specific interpretations
    
    return info if info.get('description') != 'No description available' or info.get('unit') != 'Unknown' else None


def match_excel_to_pdf(excel_columns, pdf_parameters):
    """
    Match Excel column names to PDF parameter names.
    Returns a mapping dictionary.
    """
    mapping = {}
    
    # Name mapping dictionary for Excel to PDF parameter matching
    name_variations = {
        # Body Composition
        'Bone mineral density': 'Bone Mineral Density',
        'Visceral Fat Index (raw value from DEXA)': 'Visceral Adipose Tissue',
        'Fat percentage': 'Body Fat Percentage',
        'Fat mass index': 'Fat Mass Index',
        'ALMI': 'Appendicular Lean Mass Index',
        'Muscle Mass Index (LMI)': 'Lean Mass Index',
        
        # Physical Performance
        'Vo2Max': 'VO2max',
        'HR max': 'HR max',
        'HR at VT1': 'HR at VT1',
        'HR at VT2': 'HR at VT2',
        'Counter movement jump': 'Counter movement jump',
        'Y-Balance Composite Score': 'Y-Balance Composite Score',
        'Gripstrength Rechts': 'Hand Grip right',  # Will need to handle left separately
        'Gripstrength Links': 'Hand Grip left',
        
        # HRV
        'HRV Gesamt score': 'HRV Gesamt score',
        'HRV physical activity score': 'HRV physical activity score',
        'HRV Sleep score': 'HRV Sleep score',
        'HRV Stress score': 'HRV Stress score',
        
        # Blood Biomarkers
        'Homocystein': 'Homocystein',
        'Protien': 'Protein',
        'Tesosterone': 'Testosteron',  # Note: PDF uses "Testosteron" (German spelling)
        'Fasting insulin': 'Fasting insulin',
        'HOMA Index': 'HOMA Index',
        'Vit D': 'Vit D',
        'Vit B12': 'Vit B12',
        'RDW': 'RDW',
        'hsCRP': 'hsCRP',
        'ASAT': 'ASAT',
        'ALAT': 'ALAT',
        'HbA1c': 'HbA1c',
        'Fasting glucose': 'Glucose fasted',
        'Cystatin C': 'Cystatin C',
        'HDL': 'HDL',
        'LDL': 'LDL',
        'Triglycerides': 'Triglyceride',
        'ApoB': 'ApoB',
        'Omega 3 Index': 'Omega-3 Index',
        'Selenium': 'Selenium',
    }
    
    # Normalize PDF parameter names for matching (create lowercase versions)
    pdf_lowercase_map = {name.lower(): name for name in pdf_parameters.keys()}
    
    for excel_col in excel_columns:
        if pd.notna(excel_col) and str(excel_col).strip():
            excel_col_clean = str(excel_col).strip()
            matched = False
            
            # 1. Try direct match
            if excel_col_clean in pdf_parameters:
                mapping[excel_col_clean] = excel_col_clean
                matched = True
            
            # 2. Try variation match
            elif excel_col_clean in name_variations:
                pdf_name = name_variations[excel_col_clean]
                if pdf_name in pdf_parameters:
                    mapping[excel_col_clean] = pdf_name
                    matched = True
            
            # 3. Try case-insensitive exact match
            elif not matched:
                excel_lower = excel_col_clean.lower()
                if excel_lower in pdf_lowercase_map:
                    mapping[excel_col_clean] = pdf_lowercase_map[excel_lower]
                    matched = True
            
            # 4. Try fuzzy matching (handle spaces vs hyphens, etc.)
            elif not matched:
                # Normalize both names for comparison (remove hyphens, spaces, case)
                excel_normalized = re.sub(r'[-\s]+', '', excel_col_clean.lower())
                for pdf_name in pdf_parameters.keys():
                    pdf_normalized = re.sub(r'[-\s]+', '', pdf_name.lower())
                    if excel_normalized == pdf_normalized:
                        mapping[excel_col_clean] = pdf_name
                        matched = True
                        break
            
            # 4. Try fuzzy matching (partial match)
            if not matched:
                excel_lower = excel_col_clean.lower()
                best_match = None
                best_score = 0
                
                for pdf_name in pdf_parameters.keys():
                    pdf_lower = pdf_name.lower()
                    
                    # Check if one contains the other (with minimum length)
                    if len(excel_lower) >= 5 and len(pdf_lower) >= 5:
                        if excel_lower in pdf_lower or pdf_lower in excel_lower:
                            # Score based on length of match
                            match_len = min(len(excel_lower), len(pdf_lower))
                            if match_len > best_score:
                                best_score = match_len
                                best_match = pdf_name
                
                if best_match:
                    mapping[excel_col_clean] = best_match
    
    return mapping


def create_parameter_dictionary():
    """Create parameter dictionary from Excel and PDF."""
    print("Loading Excel column names...")
    section_headers, actual_column_names = load_column_names()
    
    print("Extracting parameters from PDF report...")
    pdf_parameters = extract_pdf_parameters()
    print(f"  Found {len(pdf_parameters)} parameters in PDF")
    
    print("Matching Excel columns to PDF parameters...")
    column_mapping = match_excel_to_pdf(actual_column_names, pdf_parameters)
    print(f"  Matched {len(column_mapping)} columns")
    
    # Create dictionary structure
    parameter_dict = {
        "metadata": {
            "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_parameters": 0,  # Will be updated later
            "parameters_with_pdf_info": 0,  # Will be updated later
            "pdf_source": "005bd16b-bceb-4149-8be3-87a2a60520e3.pdf"
        },
        "sections": {},
        "parameters": {}
    }
    
    # Build sections from actual Excel section headers
    # Standardize section names and handle special cases
    section_name_map = {
        'Demographic': 'Demographic',
        'anamnese Fragebogen ': 'Anamnese Questionnaire',
        'anamnese Fragebogen': 'Anamnese Questionnaire',  # Without trailing space
        'Body composition': 'Body Composition',
        'Blood Biomarkers': 'Blood Biomarkers', 
        'Physiologisch': 'Physiological',
        'Genetic Priority (High, Medium, Low)': 'Genetic Priority (High, Medium, Low)',
        'Biologisches Alter': 'Biological Age',
        'mental health questionnaires': 'Mental Health Questionnaires',
        'Retest Questionnaire': 'Retest Questionnaire'
    }
    
    # Build section mapping from Excel headers
    sections_by_column = {}
    for i, section_header in enumerate(section_headers):
        if pd.notna(section_header):
            section_header_clean = str(section_header).strip()
            standardized_section = section_name_map.get(section_header_clean, section_header_clean)
            sections_by_column[i] = standardized_section
    
    # Process each column
    parameter_entries = {}  # (section, name) -> param_entry
    parameter_name_counts = {}  # Track how many times each parameter name appears
    
    # First pass: count occurrences of each parameter name
    for i, col_name in enumerate(actual_column_names):
        if pd.notna(col_name) and str(col_name).strip():
            col_name_clean = str(col_name).strip()
            # Fix typos
            if col_name_clean == 'city':
                col_name_clean = 'City'
            elif col_name_clean == 'Protien':
                col_name_clean = 'Protein'
            elif col_name_clean == 'Tesosterone':
                col_name_clean = 'Testosterone'
            
            parameter_name_counts[col_name_clean] = parameter_name_counts.get(col_name_clean, 0) + 1
    
    for i, col_name in enumerate(actual_column_names):
        if pd.notna(col_name) and str(col_name).strip() and str(col_name).strip() not in ['nan', '']:
            col_name_clean = str(col_name).strip()
            
            # Fix typos
            if col_name_clean == 'city ' or col_name_clean == 'city':
                col_name_clean = 'City'
            elif col_name_clean == 'Country ':
                col_name_clean = 'Country'
            elif col_name_clean == 'Protien':
                col_name_clean = 'Protein'
            elif col_name_clean == 'Tesosterone':
                col_name_clean = 'Testosterone'
            elif col_name_clean in ['Gripstrength Rechts ', 'Gripstrength Links ', 'HRV Gesamt score ', 'HRV physical activity score ', 'HRV Sleep score ', 'HRV Stress score ']:
                col_name_clean = col_name_clean.strip()
            
            # Find which section this column belongs to
            section_name = sections_by_column.get(i, 'Unknown')
            
            # Special case: Longevity Score should be its own section
            if col_name_clean == 'Longevity Score':
                section_name = 'Longevity Score'
            
            # Add suffix to distinguish duplicate parameters
            # Map of (parameter_name, section) -> suffix
            duplicate_suffixes = {
                ('Wie würden Sie Ihren Schlaf bewerten?', 'Anamnese Questionnaire'): '_initial',
                ('Wie würden Sie Ihren Schlaf bewerten?', 'Retest Questionnaire'): '_retest',
                ('Wie würden Sie Ihren momentanen Schlaf bewerten?', 'Retest Questionnaire'): '_retest',
                ('Wie bewerten Sie Ihr Stresslevel in den letzten 3 Monaten?', 'Anamnese Questionnaire'): '_initial',
                ('Wie bewerten Sie Ihr Stresslevel in den letzten 3 Monaten?', 'Mental Health Questionnaires'): '_mental',
                ('Wie bewerten Sie Ihr Stresslevel in den letzten 3 Monaten?', 'Retest Questionnaire'): '_retest',
                ('Haben Sie bestehende medizinische Probleme oder chronische Krankheiten (unabhängig davon, ob sie behandelt werden oder nicht)?', 'Anamnese Questionnaire'): '_initial',
                ('Haben Sie bestehende medizinische Probleme oder chronische Krankheiten (unabhängig davon, ob sie behandelt werden oder nicht)?', 'Retest Questionnaire'): '_retest',
                ('Wie würden Sie Ihr Energieniveau in der letzten Woche bewerten?', 'Anamnese Questionnaire'): '_initial',
                ('Wie würden Sie Ihr Energieniveau in der letzten Woche bewerten?', 'Retest Questionnaire'): '_retest',
                ('Wie würden Sie Ihren allgemeinen Gesundheitszustand bewerten?', 'Anamnese Questionnaire'): '_initial',
                ('Wie würden Sie Ihren allgemeinen Gesundheitszustand bewerten?', 'Retest Questionnaire'): '_retest',
                ('Vit D', 'Blood Biomarkers'): '_blood',
                ('Vit D', 'Genetic Priority (High, Medium, Low)'): '_genetic',
            }
            
            # Check if this parameter needs a suffix
            suffix = duplicate_suffixes.get((col_name_clean, section_name), '')
            if not suffix and parameter_name_counts.get(col_name_clean, 0) > 1:
                # If parameter appears multiple times but no specific suffix defined,
                # add section-based suffix
                if section_name == 'Retest Questionnaire':
                    suffix = '_retest'
                elif section_name == 'Mental Health Questionnaires':
                    suffix = '_mental'
                elif section_name == 'Anamnese Questionnaire':
                    suffix = '_initial'
            
            # Store original column name for section list (must match Excel exactly)
            original_col_name = col_name_clean
            
            # Add suffix to parameter name if needed (for dictionary key only)
            if suffix:
                col_name_clean = col_name_clean + suffix
            
            # Get PDF information if available
            pdf_info = None
            # Handle parameters with suffixes (e.g., "Vit D_blood" -> "Vit D")
            base_col_name = col_name_clean
            if '_' in col_name_clean:
                # Try to match without suffix first
                base_col_name = col_name_clean.split('_')[0]
            
            if col_name_clean in column_mapping:
                pdf_param_name = column_mapping[col_name_clean]
                if pdf_param_name in pdf_parameters:
                    pdf_info = pdf_parameters[pdf_param_name]
            elif base_col_name in column_mapping:
                # Try matching without suffix
                pdf_param_name = column_mapping[base_col_name]
                if pdf_param_name in pdf_parameters:
                    pdf_info = pdf_parameters[pdf_param_name]
            
            # Create parameter entry - only include fields with actual values
            # Don't include column_name or section since they're in the composite key
            param_entry = {
                "column_index": i,
            }
            
            # Add PDF information if available
            if pdf_info:
                description = pdf_info.get('description', '').strip()
                unit = pdf_info.get('unit', '').strip()
                
                if description and description != 'No description available':
                    param_entry["description"] = description
                
                if unit and unit != 'Unknown':
                    # Clean up unit - remove "in " prefix if present
                    if unit.startswith('in '):
                        unit = unit[3:].strip()
                    # Normalize common unit formats
                    if unit == 'kg/m2' or unit.lower() == 'kg/m2':
                        unit = 'kg/m²'
                    elif unit == 'g/cm2' or unit.lower() == 'g/cm2':
                        unit = 'g/cm²'
                    elif unit == 'g/cm3' or unit.lower() == 'g/cm3':
                        unit = 'g/cm³'
                    # Limit unit length (should be short)
                    if len(unit) <= 20:
                        param_entry["unit"] = unit
                
                if pdf_info.get('reference_ranges'):
                    param_entry["reference_ranges"] = pdf_info['reference_ranges']
                
                if pdf_info.get('reference_range_note'):
                    param_entry["reference_range_note"] = pdf_info['reference_range_note']
                
                if pdf_info.get('unit_note'):
                    param_entry["unit_note"] = pdf_info['unit_note']
                
                if pdf_info.get('interpretation'):
                    interpretation = pdf_info['interpretation'].strip()
                    if interpretation:
                        # Limit interpretation length
                        if len(interpretation) > 500:
                            interpretation = interpretation[:500] + "..."
                        param_entry["interpretation"] = interpretation
            
            # Store with composite key (use suffixed name for unique identification)
            section_key = section_name or "Unknown"
            key = (section_key, col_name_clean)
            parameter_entries[key] = param_entry
            
            # Add to section list using ORIGINAL column name (must match Excel for analysis script)
            # This ensures the analysis script can find the columns in the DataFrame
            if section_key not in parameter_dict["sections"]:
                parameter_dict["sections"][section_key] = []
            # Use original_col_name (without suffix) for section list to match Excel
            parameter_dict["sections"][section_key].append(original_col_name)
    
    # Store all parameter entries
    # Use composite key (section::name) as primary key to avoid duplicates
    # This ensures each parameter is stored only once, even if the same name appears in multiple sections
    parameters_with_pdf_info = 0
    for key, param_entry in parameter_entries.items():
        section_name, col_name = key
        composite_key = f"{section_name}::{col_name}"
        
        # Count parameters with PDF information
        if 'description' in param_entry or 'unit' in param_entry:
            parameters_with_pdf_info += 1
        
        # Store only with composite key to avoid duplicates
        parameter_dict["parameters"][composite_key] = param_entry
    
    # Update metadata
    parameter_dict["metadata"]["total_parameters"] = len(parameter_dict["parameters"])
    parameter_dict["metadata"]["parameters_with_pdf_info"] = parameters_with_pdf_info
    
    return parameter_dict


def save_dictionary(parameter_dict, output_format='both'):
    """Save dictionary to file(s)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create output directory if it doesn't exist
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    if output_format in ['json', 'both']:
        json_file = os.path.join(output_dir, f"parameter_dictionary_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(parameter_dict, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved JSON dictionary: {json_file}")
    
    if output_format in ['txt', 'both']:
        txt_file = os.path.join(output_dir, f"parameter_dictionary_{timestamp}.txt")
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("PARAMETER DICTIONARY - AYUN HEALTH DATA\n")
            f.write("=" * 80 + "\n\n")
            metadata = parameter_dict['metadata']
            f.write(f"Created: {metadata.get('created_date', 'N/A')}\n")
            f.write(f"Total Parameters: {metadata.get('total_parameters', len(parameter_dict['parameters']))}\n")
            f.write(f"Parameters with PDF Info: {metadata.get('parameters_with_pdf_info', 0)}\n")
            f.write(f"PDF Source: {metadata.get('pdf_source', 'N/A')}\n\n")
            
            # Write by sections
            for section_name, params in parameter_dict['sections'].items():
                f.write("\n" + "=" * 80 + "\n")
                f.write(f"SECTION: {section_name}\n")
                f.write("=" * 80 + "\n\n")
                
                for param_name in params:
                    composite_key = f"{section_name}::{param_name}"
                    if composite_key in parameter_dict['parameters']:
                        param = parameter_dict['parameters'][composite_key]
                    else:
                        continue
                    
                    f.write(f"Parameter: {param_name}\n")
                    f.write(f"  Column Index: {param.get('column_index', 'N/A')}\n")
                    if 'description' in param:
                        f.write(f"  Description: {param['description']}\n")
                    if 'unit' in param:
                        f.write(f"  Unit: {param['unit']}\n")
                    if 'reference_ranges' in param:
                        ranges = param['reference_ranges']
                        if len(ranges) >= 2:
                            f.write(f"  Reference Range: {ranges[0]:.2f} - {ranges[-1]:.2f}")
                            if len(ranges) > 2:
                                f.write(f" (intermediate: {', '.join(f'{r:.2f}' for r in ranges[1:-1])})")
                            f.write("\n")
                    if 'interpretation' in param:
                        f.write(f"  Interpretation: {param['interpretation']}\n")
                    f.write("\n")
        
        print(f"✓ Saved text dictionary: {txt_file}")
    
    return json_file if output_format in ['json', 'both'] else None, \
           txt_file if output_format in ['txt', 'both'] else None


def main():
    """Main function."""
    print("=" * 80)
    print("CREATING PARAMETER DICTIONARY FROM PDF REPORT")
    print("=" * 80)
    print("\nThis script extracts parameter information from the PDF report")
    print("and matches it with Excel column names.\n")
    
    parameter_dict = create_parameter_dictionary()
    
    print(f"\n✓ Created dictionary with {len(parameter_dict['parameters'])} parameters")
    print(f"✓ Organized into {len(parameter_dict['sections'])} sections")
    
    # Count parameters with PDF information
    pdf_enhanced = sum(1 for p in parameter_dict['parameters'].values() 
                      if isinstance(p, dict) and ('description' in p or 'unit' in p))
    print(f"✓ {pdf_enhanced} parameters enhanced with PDF information")
    
    # Save dictionary
    json_file, txt_file = save_dictionary(parameter_dict, output_format='both')
    
    print("\n" + "=" * 80)
    print("DICTIONARY CREATION COMPLETE")
    print("=" * 80)
    print(f"\nFiles created:")
    print(f"  - {json_file}")
    print(f"  - {txt_file}")


if __name__ == "__main__":
    main()
