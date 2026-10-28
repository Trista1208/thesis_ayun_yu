from __future__ import annotations

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, Field

from api.routes.auth import MemberSession
from api.deps import load_env

load_env()

from backend.documents.pdf_extractor import extract_from_bytes, to_member_dict  # noqa: E402
from backend.ai import chatbot as cb  # noqa: E402
from backend.documents.text_intake import MAX_TEXT_CHARS, parse_free_text  # noqa: E402

router = APIRouter(prefix="/extract", tags=["extract"])


@router.get("/status")
def extract_status():
    return {"configured": cb.is_configured(), "model": cb.MODEL}


@router.post("")
async def extract_file(session: MemberSession, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    data = await file.read()
    extracted = extract_from_bytes(data, file.filename)
    if not extracted.fields_found and extracted.warnings:
        return {
            "ok": False,
            "warnings": extracted.warnings,
            "member_data": {},
        }
    member_data = to_member_dict(extracted)
    user_warnings = [w for w in extracted.warnings if not w.startswith("_llm_")]
    return {
        "ok": True,
        "filename": file.filename,
        "warnings": user_warnings,
        "fields_found": extracted.fields_found,
        "field_count": len(member_data),
        "member_data": member_data,
        "age": extracted.age,
        "sex": extracted.sex,
    }


class TextIntake(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_CHARS)


@router.post("/text")
def extract_text(session: MemberSession, body: TextIntake):
    """Propose structured fields from pasted text. The member reviews them before saving."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Text is empty")
    result = parse_free_text(body.text)
    fields = list(result["member_data"]) + list(result["personal_profile"])
    return {"ok": bool(fields), **result}
