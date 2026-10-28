#!/usr/bin/env python3
"""
Update parameter dictionary with information from the PDF report.
Extracts descriptions, normal ranges, and clinical significance from PDF text.
"""

import json
import re
import os
import glob
from datetime import datetime
from pathlib import Path

def load_existing_dictionary():
    """Load the existing parameter dictionary."""
    # Priority order: cleaned > updated > timestamped
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

def extract_pdf_information():
    """Extract parameter information from the PDF text."""
    pdf_text_file = "005bd16b-bceb-4149-8be3-87a2a60520e3.txt"
    
    with open(pdf_text_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Dictionary to store extracted information
    pdf_info = {}
    
    # Extract information for key parameters
    # Pattern: Parameter name, unit, normal ranges, description, interpretation
    
    # VO2max
    vo2max_match = re.search(r'VO2max.*?(\d+\.\d+)\s*ml/min/kg', content, re.IGNORECASE)
    if vo2max_match:
        pdf_info['Vo2Max'] = {
            'example_value': vo2max_match.group(1),
            'unit': 'ml/min/kg',
            'description': 'Maximum Oxygen Uptake - highest rate of oxygen consumption during exercise. Gold standard measure of cardiorespiratory fitness. Higher values indicate better cardiovascular fitness and are associated with longevity.',
            'clinical_significance': 'One of the best predictors of longevity alongside grip strength. Low VO2max can contribute to fatigue during everyday tasks and limit physical performance.',
            'interpretation_guide': 'Excellent: >55 ml/min/kg (men), >45 ml/min/kg (women); Good: 45-55 (men), 35-45 (women); Fair: 35-45 (men), 25-35 (women); Poor: <35 (men), <25 (women)'
        }
    
    # Grip Strength
    grip_match = re.search(r'Grip Strength.*?(\d+\.\d+)\s*kg', content, re.IGNORECASE)
    if grip_match:
        pdf_info['Gripstrength Rechts'] = {
            'example_value': grip_match.group(1),
            'unit': 'kg',
            'description': 'Hand grip strength - one of the best predictors of longevity alongside VO2max. Reflects the strength of the upper body and entire body.',
            'clinical_significance': 'Without adequate grip strength, tasks such as carrying groceries, stowing luggage, or holding onto handrails become difficult. Used to assess frailty risk.',
            'normal_range': 'Men: 42-59 kg (varies by age); Women: 26-36 kg (varies by age)',
            'interpretation': 'Very good: >52 kg (men), >36 kg (women); Good: 47-52 (men), 32-36 (women); Fair: 42-47 (men), 28-32 (women); Below average: <42 (men), <28 (women)'
        }
        pdf_info['Gripstrength Links'] = pdf_info['Gripstrength Rechts'].copy()
    
    # ALMI
    almi_match = re.search(r'ALMI.*?(\d+\.\d+)\s*kg/m2', content, re.IGNORECASE)
    if almi_match:
        pdf_info['ALMI'] = {
            'example_value': almi_match.group(1),
            'unit': 'kg/m²',
            'description': 'Appendicular Lean Mass Index - measure of muscle mass in arms and legs relative to height. Used to assess sarcopenia risk.',
            'clinical_significance': 'A decreased ALMI value indicates a higher risk of sarcopenia, especially in individuals with little body fat. Important for maintaining independence and quality of life into old age.',
            'normal_range': 'Varies by age and sex; typically >7.26 kg/m² for men, >5.45 kg/m² for women',
            'interpretation': 'Below average: <7.26 kg/m² (men), <5.45 kg/m² (women) indicates increased sarcopenia risk'
        }
    
    # Cystatin C
    cystatin_match = re.search(r'Cystatin C.*?(\d+\.\d+)\s*mg/L', content, re.IGNORECASE)
    if cystatin_match:
        pdf_info['Cystatin C'] = {
            'example_value': cystatin_match.group(1),
            'unit': 'mg/L',
            'description': 'Protein used to assess kidney function, considered superior to creatinine. Used to calculate estimated glomerular filtration rate (eGFR).',
            'clinical_significance': 'Numerous studies have shown this parameter is linked to longevity. Higher cystatin C concentration is associated with increased risk of cancer mortality and cardiovascular mortality.',
            'normal_range': '0.5-1.2 mg/L (varies by age and sex); Optimal: <0.98 mg/L',
            'interpretation': 'Optimal: <0.98 mg/L; Normal: 0.98-1.21 mg/L; Elevated: >1.21 mg/L indicates decreased kidney function'
        }
    
    # HOMA Index
    homa_match = re.search(r'HOMA.*?(\d+\.\d+)', content, re.IGNORECASE)
    if homa_match:
        pdf_info['HOMA Index'] = {
            'example_value': homa_match.group(1),
            'unit': 'Index',
            'description': 'Homeostatic Model Assessment - measure of insulin resistance. Calculated from fasting glucose and insulin levels.',
            'clinical_significance': 'Used to assess insulin resistance and beta-cell function. Higher values indicate greater insulin resistance.',
            'normal_range': '<1.0 (normal), 1.0-2.5 (borderline), >2.5 (insulin resistant)',
            'interpretation': 'Optimal: <1.0; Borderline: 1.0-2.5; Insulin resistant: >2.5',
            'calculation': 'HOMA-IR = (Fasting Glucose × Fasting Insulin) / 405 (US units) or (Fasting Glucose × Fasting Insulin) / 22.5 (SI units)'
        }
    
    # HbA1c
    hba1c_match = re.search(r'HbA1c.*?(\d+\.\d+)\s*%', content, re.IGNORECASE)
    if hba1c_match:
        pdf_info['HbA1c'] = {
            'example_value': hba1c_match.group(1),
            'unit': '%',
            'description': 'Hemoglobin A1c - measures the percentage of hemoglobin that is glycated or coated with glucose. Reflects average blood sugar levels over 2-3 months.',
            'clinical_significance': 'Key marker for diabetes diagnosis and control. More stable than single glucose measurements which fluctuate throughout the day.',
            'normal_range': '<5.7% (normal), 5.7-6.4% (prediabetes), ≥6.5% (diabetes)',
            'interpretation': 'Normal: <5.7%; Borderline high/Prediabetes: 5.7-6.4%; Diabetes: ≥6.5%. Borderline high indicates potential risk for prediabetes.'
        }
    
    # RDW
    rdw_match = re.search(r'RDW.*?(\d+\.\d+)\s*%', content, re.IGNORECASE)
    if rdw_match:
        pdf_info['RDW'] = {
            'example_value': rdw_match.group(1),
            'unit': '%',
            'description': 'Red Cell Distribution Width - measure of variability in size of red blood cells. Helps identify anemia and provides insights into cardiovascular health.',
            'clinical_significance': 'Elevated RDW indicates greater variation in red blood cell size, associated with vitamin deficiencies (B12, folate), bone marrow disorders, chronic inflammation, and increased risk of heart disease and mortality.',
            'normal_range': '11.5-14.5%; Optimal: 12.8-13.6%',
            'interpretation': 'Optimal: 12.8-13.6%; Normal: 11.5-14.5%; Elevated: >14.5% indicates potential health issues'
        }
    
    # hsCRP
    hscrp_match = re.search(r'hsCRP.*?(\d+\.\d+)\s*mg/l', content, re.IGNORECASE)
    if hscrp_match:
        pdf_info['hsCRP'] = {
            'example_value': hscrp_match.group(1),
            'unit': 'mg/L',
            'description': 'High-sensitivity C-Reactive Protein - marker of inflammation in the body. When there is ongoing inflammatory process, the liver produces more CRP.',
            'clinical_significance': 'Elevated levels indicate chronic, low-grade inflammation associated with cardiovascular disease. Linked to increased risk of heart disease and other chronic conditions.',
            'normal_range': '<1.0 mg/L (low risk), 1.0-3.0 mg/L (average risk), >3.0 mg/L (high risk)',
            'interpretation': 'Low risk: <1.0 mg/L; Average risk: 1.0-3.0 mg/L; High risk: >3.0 mg/L. Optimal: <1.1 mg/L'
        }
    
    # Vitamin D
    vitd_match = re.search(r'Vit D.*?(\d+\.\d+)\s*µg/l', content, re.IGNORECASE)
    if vitd_match:
        pdf_info['Vit D'] = {
            'example_value': vitd_match.group(1),
            'unit': 'µg/L or ng/mL',
            'description': 'Vitamin D (25-hydroxyvitamin D) - essential for bone health, calcium absorption, and immune function.',
            'clinical_significance': 'Important for calcium absorption and immune system function. Deficiency can lead to bone health issues, weakened immune function, and other health concerns.',
            'normal_range': '>30 ng/mL (75 nmol/L) optimal, 20-30 ng/mL sufficient, <20 ng/mL deficient',
            'interpretation': 'Optimal: >30 ng/mL (75 nmol/L); Sufficient: 20-30 ng/mL (50-75 nmol/L); Deficient: <20 ng/mL (<50 nmol/L)',
            'conversion': '1 µg/L = 2.5 nmol/L; 1 ng/mL = 2.5 nmol/L'
        }
    
    # LDL
    ldl_match = re.search(r'LDL-C.*?(\d+\.\d+)\s*mmol/L', content, re.IGNORECASE)
    if ldl_match:
        pdf_info['LDL'] = {
            'example_value': ldl_match.group(1),
            'unit': 'mmol/L or mg/dL',
            'description': 'Low-Density Lipoprotein - "bad" cholesterol. Carries cholesterol from liver to cells throughout the body.',
            'clinical_significance': 'Higher levels increase cardiovascular risk. When there is too much LDL cholesterol, it can contribute to atherosclerosis (fatty deposits in arteries), leading to increased risk of heart disease and stroke.',
            'normal_range': '<2.6 mmol/L (<100 mg/dL) optimal, 2.6-3.4 mmol/L (100-129 mg/dL) near optimal, 3.4-4.1 mmol/L (130-159 mg/dL) borderline high',
            'interpretation': 'Optimal: <2.6 mmol/L (<100 mg/dL); Near optimal: 2.6-3.4 mmol/L (100-129 mg/dL); Borderline high: 3.4-4.1 mmol/L (130-159 mg/dL); High: >4.1 mmol/L (>160 mg/dL)',
            'conversion': '1 mmol/L = 38.67 mg/dL'
        }
    
    # ApoB
    apob_match = re.search(r'ApoB.*?(\d+\.\d+)\s*g/l', content, re.IGNORECASE)
    if apob_match:
        pdf_info['ApoB'] = {
            'example_value': apob_match.group(1),
            'unit': 'g/L or mg/dL',
            'description': 'Apolipoprotein B - protein component of LDL and VLDL. Better predictor of cardiovascular risk than LDL alone. More accurate marker of atherogenic particles.',
            'clinical_significance': 'Essential structural component of lipoproteins involved in carrying cholesterol and triglycerides. Elevated levels are associated with increased risk of atherosclerosis and heart disease.',
            'normal_range': '<0.81 g/L (<80 mg/dL) optimal, <1.0 g/L (<100 mg/dL) acceptable',
            'interpretation': 'Optimal: <0.81 g/L (<80 mg/dL); Acceptable: 0.81-1.0 g/L (80-100 mg/dL); Elevated: >1.0 g/L (>100 mg/dL)',
            'conversion': '1 g/L = 100 mg/dL'
        }
    
    # Omega-3 Index
    omega3_match = re.search(r'Omega-3.*?Index.*?(\d+\.\d+)', content, re.IGNORECASE)
    if omega3_match:
        pdf_info['Omega 3 Index'] = {
            'example_value': omega3_match.group(1),
            'unit': '%',
            'description': 'Percentage of omega-3 fatty acids (EPA + DHA) in red blood cell membranes. Marker of omega-3 intake and cardiovascular health.',
            'clinical_significance': 'Low levels can increase risk of cardiovascular issues, inflammation, and cognitive decline. Higher ratio of omega-3 to omega-6 fatty acids is important for cardiovascular health.',
            'normal_range': '>8% optimal, 4-8% intermediate, <4% low',
            'interpretation': 'Optimal: >8%; Intermediate: 4-8%; Low: <4% indicates deficiency. Low levels suggest need for increased intake of omega-3-rich foods (fatty fish) or supplementation.',
            'recommendations': 'Fatty fish (salmon, mackerel, herring) 2-3 times per week, or algae oil supplement to improve levels'
        }
    
    # Visceral Fat (DEXA VAT)
    vat_match = re.search(r'Dexa VAT.*?(\d+\.\d+)\s*g', content, re.IGNORECASE)
    if vat_match:
        pdf_info['Visceral Fat Index (raw value from DEXA)'] = {
            'example_value': vat_match.group(1),
            'unit': 'g',
            'description': 'Visceral Adipose Tissue (VAT) - amount of visceral (internal) fat around organs measured by DEXA scan.',
            'clinical_significance': 'Visceral fat is fat around internal organs. Higher values indicate higher health risk, including increased risk of cardiovascular disease, diabetes, and metabolic syndrome. Lower is better.',
            'normal_range': 'Varies by age and sex; typically <100g for men, <80g for women (optimal)',
            'interpretation': 'Lower is better. High visceral fat is associated with increased metabolic risk.'
        }
    
    # Longevity Score
    longevity_match = re.search(r'Longevity Score.*?(\d+\.\d+)', content, re.IGNORECASE)
    if longevity_match:
        pdf_info['Longevity Score'] = {
            'example_value': longevity_match.group(1),
            'unit': 'Score',
            'description': 'Composite score assessing longevity potential based on 15 most important individual values, weighted according to their proven value in studies. Score is adjusted to reference values of age and gender group.',
            'clinical_significance': 'Integrates the most important longevity-related values. Score of 100 points indicates values within reference ranges. Scores >100 indicate significantly better than expected for age/gender group.',
            'normal_range': '100 = average for age/gender group; >100 = better than average',
            'interpretation': '100 points = within reference values; >100 points = significantly better than expected; <100 points = below reference values',
            'components': 'Based on: VO2max, Grip Strength, DEXA VAT, ALMI, Optimism, Depression, Stress, Cystatin C, HOMA, HbA1C, RDW, hsCRP, Vit D, LDL-C, ApoB'
        }
    
    # HRV scores
    hrv_patterns = {
        'HRV Gesamt score': r'Overall Score.*?(\d+\.\d+).*?Punkten',
        'HRV physical activity score': r'Physical Activity.*?(\d+\.\d+).*?Punkten',
        'HRV Sleep score': r'Sleep.*?(\d+\.\d+).*?Punkten',
        'HRV Stress score': r'Stress and Recovery.*?(\d+\.\d+).*?Punkten'
    }
    
    for param_name, pattern in hrv_patterns.items():
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            pdf_info[param_name] = {
                'example_value': match.group(1),
                'unit': 'Score (0-100)',
                'description': f'Heart Rate Variability {param_name.replace("HRV ", "").replace(" score", "")} - measure of autonomic nervous system health',
                'normal_range': '31-50 (fair), 50-71 (good), 71-86 (very good), 86-100 (excellent)',
                'interpretation': 'Higher scores indicate better autonomic nervous system function and recovery capacity'
            }
    
    return pdf_info

def update_dictionary_with_pdf_info(dictionary, pdf_info):
    """Update the dictionary with information from PDF (handles both old and cleaned formats)."""
    updated_count = 0
    
    # Create name mapping for fuzzy matching
    name_variations = {
        'Vo2Max': 'VO2max',
        'Gripstrength Rechts': 'Hand Grip right',
        'Gripstrength Links': 'Hand Grip left',
        'Fasting glucose': 'Glucose fasted',
        'Triglycerides': 'Triglyceride',
        'Omega 3 Index': 'Omega-3 Index',
    }
    
    for param_name, pdf_data in pdf_info.items():
        # Try to find the parameter in the dictionary
        # Check both simple name and composite keys (section::name)
        found_entries = []
        
        # 1. Check simple name match
        if param_name in dictionary['parameters']:
            found_entries.append((param_name, dictionary['parameters'][param_name]))
        
        # 2. Check composite keys (section::name)
        for key in dictionary['parameters'].keys():
            if '::' in key:
                # Extract parameter name from composite key
                section_part, name_part = key.split('::', 1)
                if name_part == param_name:
                    found_entries.append((key, dictionary['parameters'][key]))
        
        # 3. Try name variations
        if not found_entries:
            for excel_name, pdf_name in name_variations.items():
                if pdf_name == param_name:
                    # Try to find excel_name in dictionary
                    for key in dictionary['parameters'].keys():
                        if '::' in key:
                            section_part, name_part = key.split('::', 1)
                            if name_part == excel_name:
                                found_entries.append((key, dictionary['parameters'][key]))
        
        # Update all found entries
        for key, param_entry in found_entries:
            was_updated = False
            
            # Update description
            if 'description' in pdf_data and pdf_data['description']:
                desc = pdf_data['description'].strip()
                if desc and desc != 'No description available':
                    param_entry['description'] = desc
                    was_updated = True
            
            # Update unit
            if 'unit' in pdf_data and pdf_data['unit']:
                unit = pdf_data['unit'].strip()
                if unit and unit != 'Unknown':
                    # Clean up unit
                    if unit.startswith('in '):
                        unit = unit[3:].strip()
                    if len(unit) <= 20:  # Reasonable unit length
                        param_entry['unit'] = unit
                        was_updated = True
            
            # Update reference ranges (convert normal_range to reference_ranges if needed)
            if 'normal_range' in pdf_data and pdf_data['normal_range']:
                param_entry['normal_range'] = pdf_data['normal_range']
                was_updated = True
            
            # Add new fields
            if 'clinical_significance' in pdf_data:
                param_entry['clinical_significance'] = pdf_data['clinical_significance']
                was_updated = True
            
            if 'interpretation' in pdf_data:
                interp = pdf_data['interpretation'].strip()
                if interp:
                    param_entry['interpretation'] = interp
                    was_updated = True
            
            if 'example_value' in pdf_data:
                param_entry['example_value'] = pdf_data['example_value']
            
            # Add any additional fields
            for pdf_key, pdf_value in pdf_data.items():
                if pdf_key not in ['description', 'normal_range', 'unit'] and pdf_key not in param_entry:
                    if isinstance(pdf_value, str):
                        pdf_value = pdf_value.strip()
                    if pdf_value:  # Only add non-empty values
                        param_entry[pdf_key] = pdf_value
                        was_updated = True
            
            if was_updated:
                updated_count += 1
    
    return updated_count

def main():
    """Main function to update the parameter dictionary."""
    print("=" * 70)
    print("UPDATING PARAMETER DICTIONARY WITH PDF INFORMATION")
    print("=" * 70)
    
    # Load existing dictionary
    print("\n1. Loading existing parameter dictionary...")
    dictionary = load_existing_dictionary()
    print(f"   Loaded dictionary with {len(dictionary['parameters'])} parameter entries")
    
    # Extract PDF information
    print("\n2. Extracting information from PDF text...")
    pdf_info = extract_pdf_information()
    print(f"   Extracted information for {len(pdf_info)} parameters")
    
    # Update dictionary
    print("\n3. Updating dictionary with PDF information...")
    updated_count = update_dictionary_with_pdf_info(dictionary, pdf_info)
    print(f"   Updated {updated_count} parameter descriptions")
    
    # Update metadata
    dictionary['metadata']['updated_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dictionary['metadata']['pdf_source'] = "005bd16b-bceb-4149-8be3-87a2a60520e3.pdf"
    dictionary['metadata']['update_notes'] = "Enhanced with descriptions, normal ranges, and clinical significance from PDF report"
    
    # Save updated dictionary
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"parameter_dictionary_updated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    print(f"\n4. Saving updated dictionary to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Successfully updated parameter dictionary!")
    print(f"  Output file: {output_file}")
    print(f"  Total parameters: {len(dictionary['parameters'])}")
    print(f"  Parameters enhanced: {len(pdf_info)}")
    
    return output_file

if __name__ == "__main__":
    main()

