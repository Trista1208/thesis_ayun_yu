"""
Report Extractor for AYUN Longevity Reports and any health/fitness PDF.

Primary method: AI (LLM) extraction — understands any lab or clinic format.
Fallback:       Flexible regex patterns for common health report layouts.
Supports file formats: PDF, TXT, Word (.docx) and JSON.
"""

from __future__ import annotations

import re
import io
import os
import json as _json
from dataclasses import dataclass, field


# ── Supported file extensions ─────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = ["pdf", "txt", "docx", "json"]
SUPPORTED_LABEL      = "PDF, TXT, Word (.docx) or JSON"


@dataclass
class ExtractedMemberData:
    """All values extracted from a member report."""
    # Demographics
    name: str = ""
    age: int | None = None
    sex: str = ""          # "Male" or "Female"

    # Body Composition
    lmi: float | None = None
    almi: float | None = None
    fat_percentage: float | None = None
    visceral_fat: float | None = None
    bmd: float | None = None          # Bone Mineral Density T-score

    # Strength
    biceps_r: float | None = None
    biceps_l: float | None = None
    triceps_r: float | None = None
    triceps_l: float | None = None
    grip_r: float | None = None
    grip_l: float | None = None

    # Lower body / stability
    cmj: float | None = None
    y_balance: float | None = None

    # CPET / aerobic
    vo2max: float | None = None
    hr_max: int | None = None
    vt1: int | None = None
    vt2: int | None = None

    # Range of Motion
    shoulder_r: float | None = None
    shoulder_l: float | None = None
    hip_r: float | None = None
    hip_l: float | None = None

    # Blood Biomarkers
    ldl: float | None = None
    hba1c: float | None = None
    hsCRP: float | None = None
    alat: float | None = None
    asat: float | None = None
    ggt: float | None = None
    triglycerides: float | None = None
    homa: float | None = None
    fasting_insulin: float | None = None
    apob: float | None = None
    cystatin_c: float | None = None
    vit_d: float | None = None

    # Extraction metadata
    warnings: list[str] = field(default_factory=list)
    fields_found: list[str] = field(default_factory=list)
    file_format: str = ""


# ── Public dispatch ───────────────────────────────────────────────────────────

def extract_from_bytes(file_bytes: bytes, filename: str) -> ExtractedMemberData:
    """Detect file type from extension and extract data."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return _extract_pdf(file_bytes)
    elif ext in ("txt", "text"):
        return _extract_txt(file_bytes)
    elif ext == "docx":
        return _extract_docx(file_bytes)
    elif ext == "json":
        return _extract_json(file_bytes)
    else:
        d = ExtractedMemberData()
        d.warnings.append(
            f"Unsupported file type '.{ext}'. Supported: {SUPPORTED_LABEL}."
        )
        return d


def extract_from_pdf_bytes(pdf_bytes: bytes) -> ExtractedMemberData:
    return _extract_pdf(pdf_bytes)


def extract_from_pdf_path(path: str) -> ExtractedMemberData:
    with open(path, "rb") as f:
        return _extract_pdf(f.read())


# ── Format-specific readers ───────────────────────────────────────────────────

def _extract_pdf(file_bytes: bytes) -> ExtractedMemberData:
    """Extract text from PDF then run smart + regex extraction.

    Reads up to 40 pages — comprehensive AYUN reports spread their data
    (body comp, VO2max, strength, blood work) across many pages, so we
    need enough coverage to find all sections.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        relevant = reader.pages[:40]
        pages = [p.extract_text() or "" for p in relevant]
        full_text = "\n".join(pages)
    except Exception as e:
        d = ExtractedMemberData()
        d.warnings.append(f"Could not read PDF: {e}")
        return d
    d = _smart_extract(full_text, pages)
    d.file_format = "PDF"
    return d


def _extract_txt(file_bytes: bytes) -> ExtractedMemberData:
    try:
        text = file_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        d = ExtractedMemberData()
        d.warnings.append(f"Could not read text file: {e}")
        return d
    pages = text.split("\f") if "\f" in text else [text]
    d = _smart_extract(text, pages)
    d.file_format = "TXT"
    return d


def _extract_docx(file_bytes: bytes) -> ExtractedMemberData:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))

        parts: list[str] = []

        # Body paragraphs
        parts += [p.text for p in doc.paragraphs if p.text.strip()]

        # All tables — label | value pairs on the same row
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append("  ".join(cells))

        # Headers and footers (sometimes contain patient info)
        for section in doc.sections:
            for hdr_ftr in [section.header, section.footer]:
                for p in hdr_ftr.paragraphs:
                    if p.text.strip():
                        parts.append(p.text)

        text = "\n".join(parts)
    except Exception as e:
        d = ExtractedMemberData()
        d.warnings.append(f"Could not read Word file: {e}")
        return d
    d = _smart_extract(text, [text])
    d.file_format = "DOCX"
    return d


# ── Smart extraction: LLM (two targeted slices) + regex ──────────────────────

# Keywords for each data domain — used to find the richest page per domain
_KW_PHYSICAL = [
    "VO2", "VO2max", "VT1", "VT2", "HR max", "Herzfrequenz",
    "LMI", "ALMI", "Lean Mass Index", "Appendicular",
    "fat", "Fett", "visceral", "Fettgewebe", "BMD", "T-score", "Z-score", "Z-Wert", "Knochendichte",
    "grip", "Handkraft", "Greifkraft", "Gripstrength",
    "bicep", "tricep", "CMJ", "Y-Balance", "shoulder", "hip",
    "Schulter", "Hüfte", "schouder", "heup",
    "Körperfett", "vetpercentage", "spiermassa",
]
_KW_LAB = [
    "LDL", "HbA1c", "ALAT", "ALT", "ASAT", "AST", "GGT", "Gamma-GT",
    "triglycerid", "Triglyzeride", "insulin", "HOMA",
    "cholesterol", "Cholesterin", "glucose", "Blutzucker",
    "ApoB", "Cystatin", "Vitamin D", "hsCRP", "CRP",
    "mmol", "U/L", "mg/dL",
]


def _best_slice(full_text: str, keywords: list[str], max_chars: int = 5000) -> str:
    """Return the max_chars window with the highest keyword density."""
    step = 400
    best_start = 0
    best_score = -1
    lo = keywords  # reference, not a copy
    tl = full_text.lower()
    for start in range(0, max(1, len(full_text) - max_chars), step):
        window_lower = tl[start: start + max_chars]
        score = sum(1 for kw in lo if kw.lower() in window_lower)
        if score > best_score:
            best_score = score
            best_start = start
    return full_text[best_start: best_start + max_chars]


def _missing_lab_fields(d: ExtractedMemberData) -> bool:
    return all(
        getattr(d, f) is None
        for f in ("ldl", "hba1c", "alat", "asat", "ggt", "triglycerides", "homa", "fasting_insulin")
    )


def _smart_extract(full_text: str, pages: list[str]) -> ExtractedMemberData:
    """
    1. Regex on full text (instant baseline).
    2. LLM on full document (first ~14k chars) — same model as Ask AI.
    3. Optional second LLM pass on lab slice if blood markers still missing.
    """
    from backend.ai import chatbot as cb

    reg_d = _regex_extract(full_text, pages)
    merged = reg_d

    if cb.is_configured():
        llm_full = _llm_extract(full_text[:14000])
        merged = _merge(llm_full, reg_d)

        if _missing_lab_fields(merged):
            lab_slice = _best_slice(full_text, _KW_LAB, max_chars=6000)
            if lab_slice.strip():
                merged = _merge(_llm_extract(lab_slice), merged)

        for w in llm_full.warnings:
            if w.startswith("_llm_error:"):
                merged.warnings.append(
                    "AI could not read part of the report — check empty fields manually."
                )
                break

    return merged


def _merge(primary: ExtractedMemberData, secondary: ExtractedMemberData) -> ExtractedMemberData:
    """Fill None fields in primary from secondary."""
    fields = [
        "name", "age", "sex",
        "lmi", "almi", "fat_percentage", "visceral_fat", "bmd",
        "biceps_r", "biceps_l", "triceps_r", "triceps_l",
        "grip_r", "grip_l", "cmj", "y_balance",
        "vo2max", "hr_max", "vt1", "vt2",
        "shoulder_r", "shoulder_l", "hip_r", "hip_l",
        "ldl", "hba1c", "hsCRP", "alat", "asat", "ggt",
        "triglycerides", "homa", "fasting_insulin", "apob",
        "cystatin_c", "vit_d",
    ]
    for f in fields:
        pv = getattr(primary, f, None)
        sv = getattr(secondary, f, None)
        if (pv is None or pv == "") and sv not in (None, ""):
            setattr(primary, f, sv)
            if f not in primary.fields_found and f in secondary.fields_found:
                primary.fields_found.append(f)
    return primary


# ── LLM extraction ────────────────────────────────────────────────────────────

_LLM_SCHEMA = """\
{
  "age": <integer or null>,
  "sex": <"Male" or "Female" or null>,
  "name": <string or null>,
  "vo2max": <float ml/min/kg or null>,
  "lmi": <float kg/m² or null>,
  "almi": <float kg/m² or null>,
  "fat_percentage": <float % or null>,
  "visceral_fat": <float or null>,
  "bmd_tscore": <float T-score or Z-score e.g. -1.2 or 1.7 or null>,
  "grip_r": <float kg or null>,
  "grip_l": <float kg or null>,
  "biceps_r": <float kg or null>,
  "biceps_l": <float kg or null>,
  "triceps_r": <float kg or null>,
  "triceps_l": <float kg or null>,
  "cmj": <float cm or null>,
  "y_balance": <float % composite or null>,
  "hr_max": <integer bpm or null>,
  "vt1": <integer bpm heart rate at ventilatory threshold 1 or null>,
  "vt2": <integer bpm heart rate at ventilatory threshold 2 or null>,
  "shoulder_r": <float degrees right shoulder flexion or null>,
  "shoulder_l": <float degrees left shoulder flexion or null>,
  "hip_r": <float degrees right hip flexion or null>,
  "hip_l": <float degrees left hip flexion or null>,
  "ldl": <float mmol/L or null>,
  "hba1c": <float % or null>,
  "hsCRP": <float mg/L or null>,
  "alat": <float U/L (also called ALT) or null>,
  "asat": <float U/L (also called AST) or null>,
  "ggt": <float U/L (also called Gamma-GT) or null>,
  "triglycerides": <float mmol/L or null>,
  "homa": <float HOMA index or null>,
  "fasting_insulin": <float or null>
}"""

_LLM_PROMPT = (
    "You are a health data extraction assistant. Extract every numeric value you can find "
    "from the report text below and return ONLY a valid JSON object.\n"
    "Rules:\n"
    "- Use null for any field not mentioned in the text.\n"
    "- Do NOT invent or estimate values — only use numbers explicitly stated.\n"
    "- Numbers may use Swiss/German format: apostrophe as thousands separator (1'686 = 1686), "
    "  comma as decimal separator (3,5 = 3.5). Convert all to plain floats.\n"
    "- The report may be in English, Dutch, German or a mix. Common equivalents:\n"
    "  age          = Alter (Jahre) / Leeftijd\n"
    "  sex          = Geschlecht (Männlich=Male, Weiblich=Female) / Geslacht\n"
    "  lmi          = Lean Mass Index  (kg/m²)\n"
    "  almi         = Appendicular Lean Mass Index  (kg/m²)\n"
    "  fat_pct      = fat % / Gesamt (%Fett) / Körperfettanteil / vetpercentage\n"
    "  visceral_fat = Geschätztes viszerales Fettgewebe (use the cm³ volume value)\n"
    "  bmd_tscore   = PREFER Z-score over T-score (Knochendichte / bone mineral density)\n"
    "                 German DEXA reports have two columns: 'T-Wert' (T-score) and 'AM Z-Wert' (age-matched Z-score).\n"
    "                 USE THE 'AM Z-Wert' value — many rows will be '-' (ignore those);\n"
    "                 extract the single NUMERIC total-body value from that column (e.g. 1.7). Can be negative.\n"
    "                 Only use T-Wert if no Z-Wert column exists.\n"
    "  grip_r/l     = Greifkraft / Handkraft rechts/links\n"
    "  vo2max       = VO2max / maximale Sauerstoffaufnahme (ml/min/kg)\n"
    "  hr_max       = maximale Herzfrequenz / HR max (bpm)\n"
    "  vt1/vt2      = aerobe/anaerobe Schwelle heart rate (bpm)\n"
    "  ldl          = LDL-Cholesterin / LDL-C (mmol/L)\n"
    "  hba1c        = HbA1c (%)\n"
    "  alat         = ALAT / ALT (U/L)\n"
    "  asat         = ASAT / AST (U/L)\n"
    "  ggt          = GGT / Gamma-GT (U/L)\n"
    "  triglycerides= Triglyzeride / Triglycerides (mmol/L)\n"
    "- Values may appear in table columns — the label may be on a different line.\n"
    "- Negative T/Z-scores (e.g. -1.5) are valid for bmd_tscore. Positive values (e.g. 1.7) are also valid.\n"
    "- For bmd_tscore: skip rows that show only '-'; use the total/overall body value.\n\n"
    "JSON schema:\n" + _LLM_SCHEMA + "\n\n"
    "IMPORTANT: Return ONLY the JSON object, no explanation, no markdown fences.\n\n"
    "Report text:\n"
)


def _llm_model() -> str:
    """Same GitHub Models endpoint + model as Ask AI (chatbot.py)."""
    try:
        from backend.ai import chatbot as cb
        return cb.MODEL
    except Exception:
        return "gpt-4o"


def _llm_extract(text: str) -> ExtractedMemberData:
    """
    AI fallback: only called when regex finds nothing.
    Hard 12-second timeout so it never blocks indefinitely.
    """
    from backend.ai import chatbot as cb

    if not cb.is_configured():
        d = ExtractedMemberData()
        d.warnings.append("_llm_skip")
        return d

    try:
        client = cb._build_client()
        response = client.chat.completions.create(
            model=_llm_model(),
            messages=[{"role": "user", "content": _LLM_PROMPT + text}],
            temperature=0,
            max_tokens=900,
            **cb.request_extras(),
        )
        raw = (response.choices[0].message.content or "").strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = _json.loads(raw)
        return _map_llm_json(data)

    except Exception as e:
        d = ExtractedMemberData()
        d.warnings.append(f"_llm_error:{e}")
        return d


def _fv(v) -> float | None:
    """Safely parse a value to float.
    Handles: Swiss apostrophe thousands (1'686), German comma decimal (3,5),
    and trailing units ('15.7 kg/m²').
    """
    if v is None:
        return None
    try:
        s = str(v).strip()
        s = s.replace("'", "")      # Swiss thousands: 1'686 → 1686
        s = s.replace(",", ".")     # German decimal:  3,5   → 3.5
        s = s.split()[0]            # strip trailing units
        return float(s)
    except (ValueError, TypeError):
        return None


def _map_llm_json(data: dict) -> ExtractedMemberData:
    """Map LLM JSON output to ExtractedMemberData."""
    d = ExtractedMemberData()

    def _f(key) -> float | None:
        return _fv(data.get(key))

    def _i(key) -> int | None:
        v = _f(key)
        return int(v) if v is not None else None

    age = _i("age")
    if age is not None and 5 < age < 120:
        d.age = age; d.fields_found.append("age")

    sex_raw = data.get("sex")
    if sex_raw and str(sex_raw).lower() not in ("null", "none", ""):
        d.sex = "Female" if str(sex_raw).lower() in ("female", "f", "weiblich", "w") else "Male"
        d.fields_found.append("sex")

    name = data.get("name")
    if name and str(name).lower() not in ("null", "none", ""):
        d.name = str(name)

    _map = [
        # (json_key,      attr_name,      is_int, valid_range)
        ("vo2max",        "vo2max",        False,  (5, 100)),
        ("lmi",           "lmi",           False,  (5, 40)),
        ("almi",          "almi",          False,  (2, 20)),
        ("fat_percentage","fat_percentage",False,  (1, 75)),
        ("visceral_fat",  "visceral_fat",  False,  (0, 2000)),
        ("bmd_tscore",    "bmd",           False,  (-5, 4)),
        ("grip_r",        "grip_r",        False,  (1, 100)),
        ("grip_l",        "grip_l",        False,  (1, 100)),
        ("biceps_r",      "biceps_r",      False,  (1, 80)),
        ("biceps_l",      "biceps_l",      False,  (1, 80)),
        ("triceps_r",     "triceps_r",     False,  (1, 60)),
        ("triceps_l",     "triceps_l",     False,  (1, 60)),
        ("cmj",           "cmj",           False,  (1, 120)),
        ("y_balance",     "y_balance",     False,  (40, 130)),
        ("hr_max",        "hr_max",        True,   (120, 230)),
        ("vt1",           "vt1",           True,   (95, 215)),
        ("vt2",           "vt2",           True,   (100, 215)),
        ("shoulder_r",    "shoulder_r",    False,  (30, 200)),
        ("shoulder_l",    "shoulder_l",    False,  (30, 200)),
        ("hip_r",         "hip_r",         False,  (20, 160)),
        ("hip_l",         "hip_l",         False,  (20, 160)),
        ("ldl",           "ldl",           False,  (0.1, 15)),
        ("hba1c",         "hba1c",         False,  (3, 20)),
        ("hsCRP",         "hsCRP",         False,  (0, 200)),
        ("alat",          "alat",          False,  (1, 2000)),
        ("asat",          "asat",          False,  (1, 2000)),
        ("ggt",           "ggt",           False,  (1, 2000)),
        ("triglycerides", "triglycerides", False,  (0.1, 20)),
        ("homa",          "homa",          False,  (0, 50)),
        ("fasting_insulin","fasting_insulin",False,(0, 500)),
    ]

    for json_key, attr, as_int, (lo, hi) in _map:
        v = _f(json_key)
        if v is not None and lo <= v <= hi:
            setattr(d, attr, int(v) if as_int else v)
            d.fields_found.append(attr)

    return d


# ── Flexible regex extraction ────────────────────────────────────────────────
#
# Handles two common pypdf output styles:
#   INLINE  "LDL-C  3.2  mmol/L"   (label and value on same line)
#   TABLE   "LDL-C\n3.2\nmmol/L"   (pypdf column-by-column extraction)
#
# Each helper tries a list of patterns in order, first match wins.

def _ff(pattern: str, text: str, flags=re.IGNORECASE) -> float | None:
    m = re.search(pattern, text, flags)
    if m:
        s = m.group(1).replace("'", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _fi(pattern: str, text: str, flags=re.IGNORECASE) -> int | None:
    m = re.search(pattern, text, flags)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


# SEP = "separator between label and value in pypdf output"
# In inline PDFs: one or more spaces/colons.  In table PDFs: newline(s).
_SEP = r"[:\s\n]+"


def _try(patterns: list[str], text: str, lo: float, hi: float) -> float | None:
    """Try each pattern, return first value inside (lo, hi)."""
    for pat in patterns:
        v = _ff(pat, text)
        if v is not None and lo < v < hi:
            return v
    return None


def _regex_extract(full_text: str, pages: list[str]) -> ExtractedMemberData:
    d = ExtractedMemberData()
    t = full_text  # shorthand

    # ── Demographics ──────────────────────────────────────────────────────────
    for pat in [
        # "Alter (Jahre): 28.5" or "Alter: 35" — skip parenthetical content
        r"(?:Age|Alter|Leeftijd)[^:\d]{0,20}" + r"[:\s]" + r"[^\d]*(\d{2,3}(?:[.,]\d)?)\b",
        r",\s*(\d{2,3})\s*years?\b",
        r"\b(\d{2,3})\s*(?:years?\s*old|j[äa]hrig)",
        r"(?:DOB|Date of Birth|Geboortedatum|Geburtsdatum)[^\d]*(\d{4})",
    ]:
        m2 = re.search(pat, t, re.IGNORECASE)
        if m2:
            try:
                v = float(m2.group(1).replace(",", "."))
                # Convert birth year to age
                if 1900 < v < 2020:
                    import datetime; v = datetime.date.today().year - int(v)
                if 10 < v < 120:
                    d.age = int(v); d.fields_found.append("age"); break
            except (ValueError, TypeError):
                pass

    for pat in [
        r"(?:Sex|Gender|Geschlecht|Geslacht|Geschl\.?)[:\s]+"
        r"(Male|Female|M(?:ännlich)?|W(?:eiblich)?|Männlich|Weiblich|Mann|Frau|Man|Vrouw)",
        r"\b(Male|Female)\b",
    ]:
        m2 = re.search(pat, t, re.IGNORECASE)
        if m2:
            sv = m2.group(1).lower()
            d.sex = "Female" if sv in ("female", "f", "weiblich", "w", "frau", "vrouw") else "Male"
            d.fields_found.append("sex"); break

    # ── VO2max ────────────────────────────────────────────────────────────────
    v = _try([
        r"VO2\s*[Mm]ax" + _SEP + r"([\d.]+)\s*ml/min/kg",
        r"VO2\s*[Mm]ax" + _SEP + r"([\d.]+)",
        r"[Mm]aximal?\s+[Oo]xygen\s+[Uu]ptake" + _SEP + r"([\d.]+)",
        r"[Aa]erobic\s+[Cc]apacity" + _SEP + r"([\d.]+)",
    ], t, 5, 100)
    if v: d.vo2max = v; d.fields_found.append("vo2max")

    # ── HR max / VT1 / VT2 ───────────────────────────────────────────────────
    v = _try([
        r"HR\s*[Mm]ax" + _SEP + r"(\d{2,3})\b",
        r"[Mm]ax(?:imal)?\s+[Hh]eart\s+[Rr]ate" + _SEP + r"(\d{2,3})",
        r"HRmax\s*[:=]\s*(\d{2,3})",
        r"[Hh]eart\s+[Rr]ate\s+[Mm]ax" + _SEP + r"(\d{2,3})",
    ], t, 120, 230)
    if v: d.hr_max = int(v); d.fields_found.append("hr_max")

    v = _try([
        r"(?:HR\s+at\s+VT1|[Hh]eart\s+[Rr]ate\s+at\s+VT1)" + _SEP + r"(\d{2,3})\b",
        r"VT1" + _SEP + r"(\d{2,3})\b",
        r"[Vv]entilatory\s+[Tt]hreshold\s*1" + _SEP + r"(\d{2,3})",
    ], t, 95, 215)
    if v: d.vt1 = int(v); d.fields_found.append("vt1")

    v = _try([
        r"(?:HR\s+at\s+VT2|[Hh]eart\s+[Rr]ate\s+at\s+VT2)" + _SEP + r"(\d{2,3})\b",
        r"VT2" + _SEP + r"(\d{2,3})\b",
        r"[Vv]entilatory\s+[Tt]hreshold\s*2" + _SEP + r"(\d{2,3})",
    ], t, 100, 215)
    if v: d.vt2 = int(v); d.fields_found.append("vt2")

    # ── Body Composition ──────────────────────────────────────────────────────
    v = _try([
        r"[Ll]ean\s+[Mm]ass\s+[Ii]ndex[:\s\n]+([\d.,]+)\s*kg/m",
        r"[Ll]ean\s+[Mm]ass\s+[Ii]ndex\s+of\s+([\d.,]+)",
        r"\bLMI\b" + _SEP + r"([\d.,]+)",
        # German: Muskelmasse-Index / Magermasse-Index
        r"(?:Mager(?:masse)?[-\s]Index|Muskelmasse[-\s]Index)[:\s\n]+([\d.,]+)",
    ], t, 5, 40)
    if v: d.lmi = v; d.fields_found.append("lmi")

    v = _try([
        r"[Aa]ppendicular\s+[Ll]ean\s+[Mm]ass\s+[Ii]ndex[:\s\n]+([\d.,]+)\s*kg/m",
        r"[Aa]ppendicular\s+[Ll]ean\s+[Mm]ass\s+[Ii]ndex\s+of\s+([\d.,]+)",
        r"\bALMI\b" + _SEP + r"([\d.,]+)",
    ], t, 2, 20)
    if v: d.almi = v; d.fields_found.append("almi")

    v = _try([
        # English
        r"(?:[Bb]ody\s+[Ff]at\s+[Pp]ercentage|[Bb]ody\s+[Ff]at\s*%|[Ff]at\s*%)" + _SEP + r"([\d.,]+)\s*%?",
        # German DEXA: "Gesamt   18.0" under "%Fett" column header
        r"%Fett[^\n]*\n[^\n]*\bGesamt\b[^\n]+([\d.,]+)",
        r"Gesamt\s+\(%Fett\)[:\s]+([\d.,]+)",
        r"[Kk]örperfett(?:anteil)?[:\s]+([\d.,]+)\s*%?",
        # Dutch
        r"[Vv]etpercentage[:\s]+([\d.,]+)",
        r"[Ff]etpercentage[:\s]+([\d.,]+)",
    ], t, 1, 75)
    if v: d.fat_percentage = v; d.fields_found.append("fat_percentage")

    v = _try([
        # English
        r"(?:[Vv]isceral\s+[Aa]dipose\s+[Tt]issue|[Vv]isceral\s+[Ff]at(?:\s+[Ii]ndex)?|[Dd]exa\s+VAT)\b[:\s]*([\d.,]+)",
        # German DEXA: "Geschätztes viszerales Fettgewebe ... 376 cm³"
        r"[Gg]esc[hä]+tztes\s+viszerales?\s+[Ff]ettgewebe[^0-9]{0,80}([\d.,]+)\s*cm",
        r"viszerales?\s+[Ff]ettgewebe[^0-9]{0,80}([\d.,]+)",
        r"[Vv]isceraal\s+[Vv]et[:\s]+([\d.,]+)",
    ], t, 0, 2000)
    if v is not None: d.visceral_fat = v; d.fields_found.append("visceral_fat")

    # ── BMD: try Z-score (age-matched) FIRST, fall back to T-score ──────────────
    #
    # German DEXA reports have two columns: "T-Wert" and "AM Z-Wert".
    # We prefer the Z-score (age-matched) because it is more relevant for
    # active adults. The column shows "-" for most body regions; the last
    # numeric entry is the total-body value.

    # 1) AM Z-Wert column (German DEXA table format)
    z_m = re.search(r"\bAM\s+Z[-\s]*Wert\b", t, re.IGNORECASE)
    if not z_m:
        z_m = re.search(r"\bZ[-\s]*Wert\b", t, re.IGNORECASE)
    if z_m:
        window = t[z_m.start(): z_m.start() + 800]
        candidates = []
        for nm in re.finditer(r"([-]?\d+[.,]\d+|[-]?\d+)", window):
            raw = nm.group(1).replace(",", ".")
            try:
                v = float(raw)
                if -6 < v < 4:
                    candidates.append(v)
            except ValueError:
                pass
        if candidates:
            # Total body is always the last row in the column
            d.bmd = candidates[-1]
            d.fields_found.append("bmd")

    # 2) Inline Z-score label (English)
    if d.bmd is None:
        for pat in [
            r"Z[-\s]*score[:\s\n]+([-]?\d+[.,]?\d*)",
            r"(?:[Bb]one\s+[Mm]ineral\s+[Dd]ensity|BMD|Knochendichte)[^-\d]{0,30}Z[-\s]*score[:\s\n]*([-]?[\d.,]+)",
        ]:
            m2 = re.search(pat, t, re.IGNORECASE)
            if m2:
                try:
                    v = float(m2.group(1).replace(",", ".").replace("'", ""))
                    if -6 < v < 4:
                        d.bmd = v; d.fields_found.append("bmd"); break
                except ValueError:
                    pass

    # 3) T-score fallback (only used when no Z-score found at all)
    if d.bmd is None:
        for pat in [
            r"(?:[Bb]one\s+[Mm]ineral\s+[Dd]ensity|BMD|Knochendichte)[^-\d]{0,30}T[-\s]*score[:\s\n]*([-]?[\d.,]+)",
            r"\bT[-\s]score[:\s\n]*([-]?[\d.,]+)",
        ]:
            m2 = re.search(pat, t, re.IGNORECASE)
            if m2:
                try:
                    v = float(m2.group(1).replace(",", ".").replace("'", ""))
                    if -6 < v < 4:
                        d.bmd = v; d.fields_found.append("bmd"); break
                except ValueError:
                    pass

    # ── Grip Strength ─────────────────────────────────────────────────────────
    v = _try([
        r"[Gg]rip(?:\s+[Ss]trength)?\s+[Rr]ight" + _SEP + r"([\d.]+)\s*kg",
        r"[Hh]and\s*[Gg]rip\s+[Rr]ight" + _SEP + r"([\d.]+)",
        r"[Gg]ripstrength\s+[Rr]echts" + _SEP + r"([\d.]+)",
        r"[Hh]andkracht\s+[Rr]echts" + _SEP + r"([\d.]+)",
    ], t, 1, 100)
    if v: d.grip_r = v; d.fields_found.append("grip_r")

    v = _try([
        r"[Gg]rip(?:\s+[Ss]trength)?\s+[Ll]eft" + _SEP + r"([\d.]+)\s*kg",
        r"[Hh]and\s*[Gg]rip\s+[Ll]eft" + _SEP + r"([\d.]+)",
        r"[Gg]ripstrength\s+[Ll]inks" + _SEP + r"([\d.]+)",
        r"[Hh]andkracht\s+[Ll]inks" + _SEP + r"([\d.]+)",
    ], t, 1, 100)
    if v: d.grip_l = v; d.fields_found.append("grip_l")

    # ── Biceps / Triceps ──────────────────────────────────────────────────────
    v = _try([
        r"[Bb]icep(?:s)?\s+(?:[Ss]trength\s+)?[Rr](?:ight|echts)" + _SEP + r"([\d.]+)",
    ], t, 1, 80)
    if v: d.biceps_r = v; d.fields_found.append("biceps_r")

    v = _try([
        r"[Bb]icep(?:s)?\s+(?:[Ss]trength\s+)?[Ll](?:eft|inks)" + _SEP + r"([\d.]+)",
    ], t, 1, 80)
    if v: d.biceps_l = v; d.fields_found.append("biceps_l")

    v = _try([
        r"[Tt]ricep(?:s)?\s+(?:[Ss]trength\s+)?[Rr](?:ight|echts)" + _SEP + r"([\d.]+)",
    ], t, 1, 60)
    if v: d.triceps_r = v; d.fields_found.append("triceps_r")

    v = _try([
        r"[Tt]ricep(?:s)?\s+(?:[Ss]trength\s+)?[Ll](?:eft|inks)" + _SEP + r"([\d.]+)",
    ], t, 1, 60)
    if v: d.triceps_l = v; d.fields_found.append("triceps_l")

    # ── Counter Movement Jump / Y-Balance ─────────────────────────────────────
    v = _try([
        r"[Cc]ounter\s+[Mm]ovement\s+[Jj]ump" + _SEP + r"([\d.]+)\s*cm",
        r"\bCMJ\b" + _SEP + r"([\d.]+)",
    ], t, 1, 120)
    if v: d.cmj = v; d.fields_found.append("cmj")

    v = _try([
        r"Y[-\s][Bb]alance\s+[Cc]omposite" + _SEP + r"([\d.]+)",
        r"Y[-\s][Bb]alance" + _SEP + r"([\d.]+)",
    ], t, 40, 130)
    if v: d.y_balance = v; d.fields_found.append("y_balance")

    # ── Range of Motion ───────────────────────────────────────────────────────
    v = _try([
        r"[Ss]houlder\s+[Ff]lexion\s+[Rr]ight" + _SEP + r"([\d.]+)",
        r"[Ss]chouder\s+[Ff]lexie\s+[Rr]echts" + _SEP + r"([\d.]+)",
    ], t, 30, 200)
    if v: d.shoulder_r = v; d.fields_found.append("shoulder_r")

    v = _try([
        r"[Ss]houlder\s+[Ff]lexion\s+[Ll]eft" + _SEP + r"([\d.]+)",
        r"[Ss]chouder\s+[Ff]lexie\s+[Ll]inks" + _SEP + r"([\d.]+)",
    ], t, 30, 200)
    if v: d.shoulder_l = v; d.fields_found.append("shoulder_l")

    v = _try([
        r"[Hh]ip\s+[Ff]lexion\s+[Rr]ight" + _SEP + r"([\d.]+)",
        r"[Hh]eup\s+[Ff]lexie\s+[Rr]echts" + _SEP + r"([\d.]+)",
    ], t, 20, 160)
    if v: d.hip_r = v; d.fields_found.append("hip_r")

    v = _try([
        r"[Hh]ip\s+[Ff]lexion\s+[Ll]eft" + _SEP + r"([\d.]+)",
        r"[Hh]eup\s+[Ff]lexie\s+[Ll]inks" + _SEP + r"([\d.]+)",
    ], t, 20, 160)
    if v: d.hip_l = v; d.fields_found.append("hip_l")

    # ── Blood Biomarkers ──────────────────────────────────────────────────────
    # Number pattern that handles both . and , decimals and ' thousands
    _N = r"([\d]['\d]*[.,]?\d*)"

    v = _try([
        r"LDL[-\s]*[Cc]holesterin?" + _SEP + _N + r"\s*mmol",
        r"LDL[-\s]*C?" + _SEP + _N + r"\s*mmol",
        r"\bLDL\b" + _SEP + _N,
        r"[Ll]ow.?[Dd]ensity\s+[Ll]ipoprotein" + _SEP + _N,
    ], t, 0.1, 15)
    if v: d.ldl = v; d.fields_found.append("ldl")

    v = _try([
        r"HbA1[Cc]" + _SEP + _N + r"\s*%?",
        r"[Gg]lycated\s+[Hh]ae?moglobin" + _SEP + _N,
        r"Glykiertes\s+H[äa]moglobin" + _SEP + _N,
    ], t, 3, 20)
    if v: d.hba1c = v; d.fields_found.append("hba1c")

    v = _try([
        r"hs[-\s]?CRP" + _SEP + _N,
        r"hsCRP" + _SEP + _N,
        r"[Cc].?[Rr]eaktives?\s+[Pp]rotein" + _SEP + _N,
        r"[Cc].?[Rr]eactive\s+[Pp]rotein" + _SEP + _N,
    ], t, 0, 500)
    if v is not None: d.hsCRP = v; d.fields_found.append("hsCRP")

    v = _try([
        r"\bALAT\b" + _SEP + _N + r"(?:\s*U/L)?",
        r"\bALT\b" + _SEP + _N + r"(?:\s*U/L)?",
        r"[Aa]lanin(?:aminotransferase)?" + _SEP + _N,
    ], t, 1, 2000)
    if v: d.alat = v; d.fields_found.append("alat")

    v = _try([
        r"\bASAT\b" + _SEP + _N + r"(?:\s*U/L)?",
        r"\bAST\b" + _SEP + _N + r"(?:\s*U/L)?",
        r"[Aa]spartat(?:aminotransferase)?" + _SEP + _N,
    ], t, 1, 2000)
    if v: d.asat = v; d.fields_found.append("asat")

    v = _try([
        r"\bGGT\b" + _SEP + _N + r"(?:\s*U/L)?",
        r"[Gg]amma[-\s]?GT" + _SEP + _N + r"(?:\s*U/L)?",
        r"[Gg]amma[-\s]?[Gg]lutamyl(?:transferase)?" + _SEP + _N,
    ], t, 1, 2000)
    if v: d.ggt = v; d.fields_found.append("ggt")

    v = _try([
        r"[Tt]riglyzeride" + _SEP + _N + r"\s*mmol",
        r"[Tt]riglycerides?" + _SEP + _N + r"\s*mmol",
        r"[Tt]riglyzeride" + _SEP + _N,
        r"[Tt]riglycerides?" + _SEP + _N,
    ], t, 0.1, 20)
    if v: d.triglycerides = v; d.fields_found.append("triglycerides")

    v = _try([
        r"HOMA(?:[-\s]IR)?" + _SEP + _N,
        r"N[üu]chtern(?:blutzucker|glukose|insulin).*?" + _N,
    ], t, 0, 50)
    if v: d.homa = v; d.fields_found.append("homa")

    v = _try([
        r"[Ff]asting\s+[Ii]nsulin" + _SEP + _N,
        r"N[üu]chterninsulin" + _SEP + _N,
    ], t, 0, 500)
    if v: d.fasting_insulin = v; d.fields_found.append("fasting_insulin")

    v = _try([r"\bApoB\b" + _SEP + _N], t, 0, 5)
    if v: d.apob = v; d.fields_found.append("apob")

    v = _try([r"[Cc]ystatin[-\s]?C" + _SEP + _N], t, 0, 20)
    if v: d.cystatin_c = v; d.fields_found.append("cystatin_c")

    v = _try([
        r"[Vv]it(?:amin)?\s+D\s*(?:25[-\s]OH)?" + _SEP + _N,
        r"25[-\s]?OH[-\s]?D" + _SEP + _N,
        r"[Cc]alciferol" + _SEP + _N,
    ], t, 1, 300)
    if v: d.vit_d = v; d.fields_found.append("vit_d")

    return d


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(file_bytes: bytes) -> ExtractedMemberData:
    try:
        data = _json.loads(file_bytes.decode("utf-8", errors="replace"))
    except Exception as e:
        d = ExtractedMemberData()
        d.warnings.append(f"Could not parse JSON: {e}")
        return d

    d = ExtractedMemberData()
    d.file_format = "JSON"

    flat: dict[str, object] = {}
    if isinstance(data, dict):
        if any("::" in str(k) for k in data):
            flat = {k.split("::")[-1].strip(): v for k, v in data.items()}
            flat.update(data)
        elif "member" in data and isinstance(data["member"], dict):
            flat = data["member"]
        elif "sections" in data:
            d.warnings.append(
                "This JSON appears to be a parameter schema, not member data. "
                "Please export member values as a flat JSON dict."
            )
            return d
        else:
            flat = data
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        for rec in data:
            k = str(rec.get("parameter", rec.get("name", rec.get("key", "")))).strip()
            v = rec.get("value", rec.get("val", None))
            if k and v is not None:
                flat[k] = v
    else:
        d.warnings.append("Unrecognised JSON structure. Expected a dict or list of records.")
        return d

    def _num(keys: list[str]) -> float | None:
        for k in keys:
            for fk, fv in flat.items():
                if fk.lower().strip() == k.lower():
                    try:
                        return float(str(fv).replace(",", ".").split()[0])
                    except (ValueError, IndexError):
                        pass
        return None

    def _str(keys: list[str]) -> str:
        for k in keys:
            for fk, fv in flat.items():
                if fk.lower().strip() == k.lower():
                    return str(fv).strip()
        return ""

    age = _num(["age", "alter", "demographic::age"])
    if age is not None:
        d.age = int(age); d.fields_found.append("age")
    sex = _str(["sex", "gender", "geschlecht", "demographic::sex"])
    if sex:
        d.sex = "Female" if sex.lower() in ("female", "f", "weiblich", "w") else "Male"
        d.fields_found.append("sex")
    name = _str(["name", "member_name", "fullname"])
    if name:
        d.name = name

    _field_map = [
        (["lmi", "lean mass index", "muscle mass index (lmi)", "body composition::muscle mass index (lmi)"], "lmi"),
        (["almi", "body composition::almi"], "almi"),
        (["fat percentage", "fat %", "body fat", "fat_percentage", "body composition::fat percentage"], "fat_percentage"),
        (["visceral fat index (raw value from dexa)", "visceral fat", "vat", "dexa vat"], "visceral_fat"),
        (["bmd", "bmd t-score", "t-score", "bone mineral density"], "bmd"),
        (["vo2max", "vo2 max", "physiological::vo2max"], "vo2max"),
        (["grip right", "gripstrength rechts", "grip_r", "physiological::gripstrength rechts"], "grip_r"),
        (["grip left", "gripstrength links", "grip_l", "physiological::gripstrength links"], "grip_l"),
        (["biceps right", "biceps r", "biceps_r", "physiological::biceps strength rechts"], "biceps_r"),
        (["biceps left", "biceps l", "biceps_l", "physiological::biceps strength links"], "biceps_l"),
        (["triceps right", "triceps r", "triceps_r", "physiological::triceps strength rechts"], "triceps_r"),
        (["triceps left", "triceps l", "triceps_l", "physiological::triceps strength links"], "triceps_l"),
        (["counter movement jump", "cmj", "physiological::counter movement jump"], "cmj"),
        (["y-balance composite score", "y balance", "ybalance", "physiological::y-balance composite score"], "y_balance"),
        (["hr max", "hrmax", "hr_max", "physiological::hr max"], "hr_max"),
        (["hr at vt1", "vt1", "hr_vt1", "physiological::hr at vt1"], "vt1"),
        (["hr at vt2", "vt2", "hr_vt2", "physiological::hr at vt2"], "vt2"),
        (["shoulder flexion right", "shoulder_r"], "shoulder_r"),
        (["shoulder flexion left", "shoulder_l"], "shoulder_l"),
        (["hip flexion right", "hip_r"], "hip_r"),
        (["hip flexion left", "hip_l"], "hip_l"),
        (["ldl", "ldl-c", "blood biomarkers::ldl"], "ldl"),
        (["hba1c", "hba1c%", "blood biomarkers::hba1c"], "hba1c"),
        (["hscrp", "hs-crp", "hsCRP"], "hsCRP"),
        (["alat", "alt", "blood biomarkers::alat"], "alat"),
        (["asat", "ast", "blood biomarkers::asat"], "asat"),
        (["ggt", "gamma-gt", "gamma gt", "blood biomarkers::ggt"], "ggt"),
        (["triglycerides", "trig"], "triglycerides"),
        (["homa index", "homa"], "homa"),
        (["fasting insulin", "insulin"], "fasting_insulin"),
        (["apob", "apo b"], "apob"),
        (["cystatin c", "cystatin_c"], "cystatin_c"),
        (["vit d", "vitamin d", "vit_d"], "vit_d"),
    ]

    for keys, attr in _field_map:
        v = _num(keys)
        if v is not None:
            if attr in ("hr_max", "vt1", "vt2"):
                setattr(d, attr, int(v))
            else:
                setattr(d, attr, v)
            d.fields_found.append(attr)

    if not d.fields_found:
        d.warnings.append(
            "No matching fields found in this JSON. "
            'Keys should match AYUN parameter names, e.g. {"Age": 35, "Sex": "Male", "Vo2Max": 42.0, ...}'
        )
    return d


# ── Result → member dict ──────────────────────────────────────────────────────

def to_member_dict(extracted: ExtractedMemberData) -> dict:
    """Convert ExtractedMemberData to the parameter dict used by the rule engine."""
    m: dict = {}

    if extracted.age is not None:
        m["Demographic::Age"] = extracted.age
    if extracted.sex:
        m["Demographic::Sex"] = extracted.sex
    if extracted.vo2max is not None:
        m["Physiological::Vo2Max"] = extracted.vo2max
    if extracted.grip_r is not None:
        m["Physiological::Gripstrength Rechts"] = extracted.grip_r
    if extracted.grip_l is not None:
        m["Physiological::Gripstrength Links"] = extracted.grip_l
    if extracted.biceps_r is not None:
        m["Physiological::Biceps Strength Rechts"] = extracted.biceps_r
    if extracted.biceps_l is not None:
        m["Physiological::Biceps Strength Links"] = extracted.biceps_l
    if extracted.triceps_r is not None:
        m["Physiological::Triceps Strength Rechts"] = extracted.triceps_r
    if extracted.triceps_l is not None:
        m["Physiological::Triceps Strength Links"] = extracted.triceps_l
    if extracted.cmj is not None:
        m["Physiological::Counter movement jump"] = extracted.cmj
    if extracted.y_balance is not None:
        m["Physiological::Y-Balance Composite Score"] = extracted.y_balance
    if extracted.hr_max is not None:
        m["Physiological::HR max"] = extracted.hr_max
    if extracted.vt1 is not None:
        m["Physiological::HR at VT1"] = extracted.vt1
    if extracted.vt2 is not None:
        m["Physiological::HR at VT2"] = extracted.vt2
    if extracted.shoulder_r is not None:
        m["Physiological::Shoulder Flexion Right"] = extracted.shoulder_r
    if extracted.shoulder_l is not None:
        m["Physiological::Shoulder Flexion Left"] = extracted.shoulder_l
    if extracted.hip_r is not None:
        m["Physiological::Hip Flexion Right"] = extracted.hip_r
    if extracted.hip_l is not None:
        m["Physiological::Hip Flexion Left"] = extracted.hip_l
    if extracted.lmi is not None:
        m["Body Composition::Muscle Mass Index (LMI)"] = extracted.lmi
    if extracted.almi is not None:
        m["Body Composition::ALMI"] = extracted.almi
    if extracted.fat_percentage is not None:
        m["Body Composition::Fat percentage"] = extracted.fat_percentage
    if extracted.visceral_fat is not None:
        m["Body Composition::Visceral Fat Index (raw value from DEXA)"] = extracted.visceral_fat
    if extracted.bmd is not None:
        m["Body Composition::Bone mineral density"] = extracted.bmd
    if extracted.ldl is not None:
        m["Blood Biomarkers::LDL"] = extracted.ldl
    if extracted.hba1c is not None:
        m["Blood Biomarkers::HbA1c"] = extracted.hba1c
    if extracted.hsCRP is not None:
        m["Blood Biomarkers::hsCRP"] = extracted.hsCRP
    if extracted.homa is not None:
        m["Blood Biomarkers::HOMA Index"] = extracted.homa
    if extracted.alat is not None:
        m["Blood Biomarkers::ALAT"] = extracted.alat
    if extracted.asat is not None:
        m["Blood Biomarkers::ASAT"] = extracted.asat
    if extracted.ggt is not None:
        m["Blood Biomarkers::GGT"] = extracted.ggt
    if extracted.triglycerides is not None:
        m["Blood Biomarkers::Triglycerides"] = extracted.triglycerides
    if extracted.fasting_insulin is not None:
        m["Blood Biomarkers::Fasting insulin"] = extracted.fasting_insulin
    if extracted.apob is not None:
        m["Blood Biomarkers::ApoB"] = extracted.apob
    if extracted.cystatin_c is not None:
        m["Blood Biomarkers::Cystatin C"] = extracted.cystatin_c

    return m
