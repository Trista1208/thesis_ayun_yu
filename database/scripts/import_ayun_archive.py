#!/usr/bin/env python3
"""
Import AYUN historical Excel data into Supabase (ayun_import_batches / ayun_import_rows).

Usage:
  python database/scripts/import_ayun_archive.py /path/to/ayun_export.xlsx --batch-name "clinic_2024"

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env (project root) or environment.
Optional: pip install pandas openpyxl
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_env = _ROOT / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from backend.storage import ayun_db


def _flatten_columns(df):
    if isinstance(df.columns, __import__("pandas").MultiIndex):
        df.columns = [
            f"{cat}::{param}" if str(cat) != "nan" and "Unnamed" not in str(cat) else str(param)
            for cat, param in df.columns
        ]
    df.columns = [str(c).replace("Unnamed: ", "Extra_") for c in df.columns]
    return df


def _row_to_json(row) -> dict:
    out = {}
    for k, v in row.items():
        try:
            import pandas as pd
            if pd.isna(v):
                continue
        except ImportError:
            if v is None:
                continue
        key = str(k)
        if hasattr(v, "isoformat"):
            out[key] = v.isoformat()
        elif hasattr(v, "item"):
            out[key] = v.item()
        else:
            out[key] = v
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Import AYUN Excel archive into Supabase")
    parser.add_argument("excel_path", help="Path to AYUN Excel export")
    parser.add_argument("--batch-name", default="", help="Label for this import batch")
    parser.add_argument("--pseudonym-column", default="", help="Column name for member pseudonym/token")
    parser.add_argument("--imported-by", default="", help="Your name or operator id")
    parser.add_argument("--sheet", default=0, help="Sheet index or name (default: first sheet)")
    args = parser.parse_args()

    if not ayun_db.is_configured():
        print("Error: set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env", file=sys.stderr)
        return 1

    try:
        import pandas as pd
    except ImportError:
        print("Error: pip install pandas openpyxl", file=sys.stderr)
        return 1

    path = Path(args.excel_path)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    print(f"Loading {path} …")
    df = pd.read_excel(path, header=[0, 1], sheet_name=args.sheet)
    df = _flatten_columns(df)
    print(f"  {len(df)} rows, {len(df.columns)} columns")

    batch_name = args.batch_name.strip() or path.stem
    rows = []
    for _, series in df.iterrows():
        row_data = _row_to_json(series)
        pseudonym = None
        if args.pseudonym_column and args.pseudonym_column in row_data:
            pseudonym = str(row_data[args.pseudonym_column])
        rows.append({"pseudonym": pseudonym, "row_data": row_data})

    count = ayun_db.import_batch(
        batch_name=batch_name,
        rows=rows,
        source_file=str(path.name),
        imported_by=args.imported_by,
    )
    if count is None:
        print("Error: import failed (check Supabase schema and credentials)", file=sys.stderr)
        return 1

    print(f"Imported {count} rows into batch '{batch_name}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
