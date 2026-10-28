#!/usr/bin/env python3
"""
Clean up an existing parameter dictionary by:
1. Removing duplicate entries (keep only composite keys)
2. Removing redundant fields (column_name, section - already in key)
3. Removing fields with "Unknown" or "No description available from PDF"
"""

import json
import sys
import glob
import os
from datetime import datetime

def cleanup_dictionary(input_file, output_file=None):
    """Clean up a parameter dictionary file."""
    print(f"Loading dictionary from: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Clean up parameters
    cleaned_params = {}
    removed_count = 0
    
    for key, param in data.get('parameters', {}).items():
        # Only keep composite keys (those with "::")
        if '::' not in key:
            removed_count += 1
            continue
        
        # Create cleaned parameter entry
        cleaned_param = {}
        
        # Keep column_index
        if 'column_index' in param:
            cleaned_param['column_index'] = param['column_index']
        
        # Only include description if it's not a placeholder
        if 'description' in param:
            desc = param['description'].strip()
            if desc and desc != 'No description available from PDF':
                cleaned_param['description'] = desc
        
        # Only include unit if it's not "Unknown"
        if 'unit' in param:
            unit = param['unit'].strip()
            if unit and unit != 'Unknown':
                # Clean up unit - remove "in " prefix if present
                if unit.startswith('in '):
                    unit = unit[3:].strip()
                # Limit unit length (should be short)
                if len(unit) <= 20:
                    cleaned_param['unit'] = unit
        
        # Include reference_ranges if present
        if 'reference_ranges' in param and param['reference_ranges']:
            cleaned_param['reference_ranges'] = param['reference_ranges']
        
        # Include reference_range_note if present
        if 'reference_range_note' in param:
            note = param['reference_range_note'].strip()
            if note:
                cleaned_param['reference_range_note'] = note
        
        # Include unit_note if present
        if 'unit_note' in param:
            note = param['unit_note'].strip()
            if note:
                cleaned_param['unit_note'] = note
        
        # Include interpretation if present and not empty
        if 'interpretation' in param:
            interp = param['interpretation'].strip()
            if interp:
                cleaned_param['interpretation'] = interp
        
        # Only add if it has at least column_index
        if cleaned_param:
            cleaned_params[key] = cleaned_param
    
    # Update data
    data['parameters'] = cleaned_params
    
    # Update metadata
    if 'metadata' not in data:
        data['metadata'] = {}
    
    data['metadata']['total_parameters'] = len(cleaned_params)
    data['metadata']['parameters_with_pdf_info'] = sum(
        1 for p in cleaned_params.values() 
        if 'description' in p or 'unit' in p
    )
    data['metadata']['cleaned_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data['metadata']['original_file'] = input_file
    
    # Remove unnecessary metadata fields
    if 'total_columns' in data['metadata']:
        del data['metadata']['total_columns']
    if 'dataset_name' in data['metadata']:
        del data['metadata']['dataset_name']
    
    # Save cleaned dictionary
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    if output_file is None:
        # Create output filename
        base_name = os.path.basename(input_file).replace('.json', '')
        output_file = os.path.join(output_dir, f"{base_name}_cleaned.json")
    
    print(f"Saving cleaned dictionary to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Cleaned dictionary:")
    print(f"  - Removed {removed_count} duplicate entries")
    print(f"  - Total parameters: {len(cleaned_params)}")
    print(f"  - Parameters with PDF info: {data['metadata']['parameters_with_pdf_info']}")
    
    return output_file


def create_cleaned_text_file(json_file, txt_file=None):
    """Create a cleaned text version of the dictionary."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if txt_file is None:
        # If json_file already has _cleaned, don't add another one
        if json_file.endswith('_cleaned.json'):
            txt_file = json_file.replace('_cleaned.json', '_cleaned.txt')
        else:
            txt_file = json_file.replace('.json', '_cleaned.txt')
        
        # Ensure text file is also in output directory
        output_dir = "output"
        if os.path.dirname(txt_file) != output_dir:
            txt_file = os.path.join(output_dir, os.path.basename(txt_file))
    
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("PARAMETER DICTIONARY - AYUN HEALTH DATA (CLEANED)\n")
        f.write("=" * 80 + "\n\n")
        
        metadata = data.get('metadata', {})
        f.write(f"Created: {metadata.get('created_date', 'N/A')}\n")
        f.write(f"Cleaned: {metadata.get('cleaned_date', 'N/A')}\n")
        f.write(f"Total Parameters: {metadata.get('total_parameters', 0)}\n")
        f.write(f"Parameters with PDF Info: {metadata.get('parameters_with_pdf_info', 0)}\n")
        f.write(f"PDF Source: {metadata.get('pdf_source', 'N/A')}\n\n")
        
        # Write by sections
        for section_name, params in data.get('sections', {}).items():
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"SECTION: {section_name}\n")
            f.write("=" * 80 + "\n\n")
            
            for param_name in params:
                composite_key = f"{section_name}::{param_name}"
                if composite_key in data['parameters']:
                    param = data['parameters'][composite_key]
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
                
                if 'reference_range_note' in param:
                    f.write(f"  Reference Range Note: {param['reference_range_note']}\n")
                
                if 'unit_note' in param:
                    f.write(f"  Unit Note: {param['unit_note']}\n")
                
                if 'interpretation' in param:
                    f.write(f"  Interpretation: {param['interpretation']}\n")
                
                f.write("\n")
    
    print(f"✓ Created cleaned text file: {txt_file}")
    return txt_file


def main():
    """Main function."""
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # Find the most recent dictionary file
        # Check in output directory first, then fallback to root
        output_dir = "output"
        dict_files = glob.glob(os.path.join(output_dir, "parameter_dictionary_*.json"))
        if not dict_files:
            dict_files = glob.glob("parameter_dictionary_*.json")
        if not dict_files:
            print("Error: No parameter dictionary files found!")
            sys.exit(1)
        
        # Sort by modification time, get most recent
        dict_files.sort(key=os.path.getmtime, reverse=True)
        input_file = dict_files[0]
        print(f"Using most recent dictionary: {input_file}")
    
    if not input_file.endswith('.json'):
        print(f"Error: Input file must be a JSON file: {input_file}")
        sys.exit(1)
    
    # Clean up dictionary
    cleaned_json = cleanup_dictionary(input_file)
    
    # Create cleaned text file
    create_cleaned_text_file(cleaned_json)
    
    print("\n" + "=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()

