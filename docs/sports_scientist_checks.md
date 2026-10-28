# What the Sports Scientist Checks (AYUN)

This document summarises the inputs the sports scientist uses and how they are reflected in the recommendation engine and app.

## 1. DEXA (Body Composition)

- **Muscle Mass Index (LMI)**, **ALMI** — lean mass relative to height  
- **Fat percentage**, **Visceral Fat Index** — fat distribution  
- **Bone mineral density (BMD)** — T-score from DEXA  

*In the app:* Body Composition section in sidebar and PDF extraction; reference ranges and recommendation conditions in `sports_health_recommendations.yml`.

## 2. Physical Testing

- **Upper body strength:** biceps, triceps, **handgrip** (left/right)  
- **Lower body:** **Counter movement jump (CMJ)**  
- **Stability:** **Y-Balance test** (composite score)  
- **Cardiorespiratory:** **VO2max**; **HR at VT1, VT2, HR max** (training zones)  
- **Range of motion** — not yet in parameter dictionary; can be added later  

*In the app:* Physiological section (VO2max, grip strength, CMJ, Y-Balance, HR at VT1/VT2/HR max); training zones computed from VT1/VT2.

## 3. Genetic Testing

- **Bone health** — genetically prone to lose bone density → bone health becomes a **top priority** (weight-bearing, resistance, calcium, Vitamin D, DEXA monitoring).  

*In the app:* Recommendation block *"Genetic Bone Loss Risk - Prioritise Bone Health"* triggers when `Genetic Priority (High, Medium, Low)::Bone health` is **High**. Present in all age/gender groups in the YAML.

## 4. Blood Parameters

- **LDL** — high cholesterol; combine aerobic (150+ min/week) + resistance + nutrition (less saturated fat, more fibre).  
- **HbA1c** — high blood sugar / prediabetes; moderate endurance + resistance + limit refined carbs; recheck in 3 months.  
- **ALAT, ASAT** (and **GGT** if available) — possible **fatty liver** → **immediate** start with **moderate endurance training** (e.g. Zone 2, 3–5x/week) and **adjust nutrition** (reduce refined carbs, increase fibre, limit alcohol); recheck in 8–12 weeks.  

*In the app:* YAML recommendation blocks:

- *"Elevated LDL Cholesterol"* — when `Blood Biomarkers::LDL` > 3.0 (mmol/L).  
- *"Elevated HbA1c / Blood Sugar"* — when `Blood Biomarkers::HbA1c` ≥ 5.7%.  
- *"Possible Fatty Liver - Start Moderate Endurance Now"* (Critical) — when `Blood Biomarkers::ALAT` > 20 or `Blood Biomarkers::ASAT` > 40 (U/L).  

These blocks are present for all age groups and both sexes.  
*Note:* GGT is not in the current Excel/parameter dictionary; it can be added when available.

## 5. Summary for Stakeholders

The sports scientist integrates:

1. **DEXA** (body composition + bone density)  
2. **Physical testing** (strength, power, stability, VO2max, training zones)  
3. **Genetics** (e.g. bone health priority)  
4. **Blood** (LDL, HbA1c, liver enzymes)  

The app and YAML now include all of the above. Blood and genetic parameters can be added to the **sidebar** and **PDF extraction** in a next step so they are collected and passed into the rule engine for personalised recommendations.
