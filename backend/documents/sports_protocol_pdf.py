"""Branded sports-performance protocol PDF for members and clinicians."""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

TEAL = HexColor("#2c6771")
TEAL_DARK = HexColor("#1a4d35")
GREEN = HexColor("#2e7d52")
INK = HexColor("#1c241f")
MUTED = HexColor("#3d4740")
SOFT = HexColor("#5a6356")
RULE = HexColor("#e4ebe6")
PAPER = HexColor("#f4faf7")
WASH = HexColor("#e7f3ec")

_LOGO = Path(__file__).resolve().parent / "ayun-logo-transparent.png"

_ACTION_RATINGS = {"below_average", "poor", "elevated", "high"}
_PROTOCOL_PARAMS = {
    "low_vo2max": ["Physiological::Vo2Max"],
    "high_body_fat": [
        "Body Composition::Fat percentage",
        "Body Composition::Visceral Fat Index (raw value from DEXA)",
    ],
    "low_bone_density": ["Body Composition::Bone mineral density"],
    "low_strength_muscle": [
        "Physiological::Gripstrength Rechts",
        "Physiological::Gripstrength Links",
        "Body Composition::Muscle Mass Index (LMI)",
        "Body Composition::ALMI",
    ],
    "elevated_hba1c": ["Blood Biomarkers::HbA1c"],
    "possible_fatty_liver": [
        "Blood Biomarkers::ALAT",
        "Blood Biomarkers::ASAT",
        "Blood Biomarkers::GGT",
    ],
}
_ROW_RULES = [
    ("Follow-up", re.compile(r"\b(retest|recheck|re-?assess|monitor|consult|referral|physician|physiotherap|medical review|clinician|DEXA|screening|check-?up|doctor)\b", re.I)),
    ("Nutrition", re.compile(r"\b(protein|diet|calori|eat|meal|fibre|fiber|carbohydrat|sugar|omega|vitamin|calcium|saturated fat|g/kg|kcal)\b", re.I)),
    ("Cardio", re.compile(r"\b(zone 2|cardio|endurance|aerobic|interval|hiit|vt2|vt1|walk|jog|running|cycling|swim)\b", re.I)),
    ("Mobility", re.compile(r"\b(mobility|stretch|flexib|range of motion|yoga|pilates|balance)\b", re.I)),
    ("Training", re.compile(r"\b(strength|resistance|training|lift|overload|squat|deadlift|press|row|pull|push|reps|sets|sessions?)\b", re.I)),
    ("Lifestyle", re.compile(r"\b(sleep|alcohol|stress|smok|recovery|hrv|rest)\b", re.I)),
]
_OWN_LABEL = re.compile(r"^(Frequency|Intensity|Duration|Volume|Rest):\s*", re.I)
_RATING_LABELS = {
    "excellent": "excellent",
    "good": "good",
    "average": "average",
    "below_average": "a little below AYUN target",
    "poor": "below AYUN target",
    "elevated": "slightly above AYUN target",
    "high": "above AYUN target",
    "low": "very low",
}
_ROW_ORDER = [
    "Frequency", "Intensity", "Duration", "Volume", "Rest",
    "Training", "Cardio", "Mobility", "Nutrition", "Lifestyle", "Guidance", "Follow-up",
]


def _plain(value: Any) -> str:
    text = str(value or "")
    for src, dst in {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u00a0": " ",
        "\u2026": "...",
    }.items():
        text = text.replace(src, dst)
    return " ".join(text.replace("\n", " ").split())


def _latin(value: Any) -> str:
    return _plain(value).encode("latin-1", "replace").decode("latin-1")


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    words = _latin(text).split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if pdfmetrics.stringWidth(trial, font, size) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _items(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parts = re.split(r"[\n]+", raw)
    elif isinstance(raw, list):
        parts = [str(item) for item in raw]
    else:
        return []
    cleaned = []
    for part in parts:
        line = re.sub(r"^[\s•\-]+", "", _plain(part)).strip()
        if line:
            cleaned.append(line)
    return cleaned


def _layout_rows(items: list[str]) -> list[tuple[str, str]]:
    grouped: dict[str, list[str]] = {}
    for item in items:
        own = _OWN_LABEL.match(item)
        if own:
            label = own.group(1).title()
            text = item[own.end():].strip()
        else:
            label = next((name for name, rule in _ROW_RULES if rule.search(item)), "Guidance")
            text = item
        grouped.setdefault(label, []).append(text)
    return [(label, " ".join(grouped[label])) for label in _ROW_ORDER if label in grouped]


def _fmt_date(iso: str) -> str:
    if not iso:
        return datetime.now().strftime("%d.%m.%Y")
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except ValueError:
        return datetime.now().strftime("%d.%m.%Y")


def _age(member_data: dict[str, Any]) -> str:
    age = (member_data or {}).get("Demographic::Age")
    if age is None or age == "":
        return ""
    try:
        number = int(float(age))
    except (TypeError, ValueError):
        return _plain(age)
    unit = "year" if number == 1 else "years"
    return f"{number} {unit}"


def _goals(profile: dict[str, Any]) -> str:
    raw = (profile or {}).get("goals") or []
    if isinstance(raw, str):
        raw = [raw]
    parts = [_plain(goal) for goal in raw if _plain(goal)]
    if parts:
        return " ".join(parts)
    return (
        "Build strength, endurance, and recovery with training that stays specific, "
        "progressive, and sustainable."
    )


def _protocol_indicated(key: str, ratings: list[dict[str, Any]]) -> bool:
    params = _PROTOCOL_PARAMS.get(key)
    if not params:
        return True
    relevant = [
        row for row in ratings
        if row.get("parameter") in params and row.get("value") is not None
    ]
    if not relevant:
        return False
    return any(str(row.get("rating") or "").lower() in _ACTION_RATINGS for row in relevant)


def _recommendation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _plain(row.get("title")),
        "priority": _plain(row.get("reviewed_priority") or row.get("priority") or row.get("original_priority") or "Medium"),
        "category": _plain(row.get("category")),
        "description": _plain(row.get("description")),
        "action_items": _items(row.get("action_items")),
        "notes": _plain(row.get("clinician_notes") or row.get("notes")),
        "templates": [
            {
                "title": _plain(template.get("title")),
                "summary": _plain(template.get("summary")),
            }
            for template in (row.get("templates") or [])
            if _plain(template.get("title") or template.get("summary"))
        ],
        "source": _plain(row.get("source")),
    }


def _active(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out = []
    for row in rows or []:
        if row.get("removed"):
            continue
        item = _recommendation(row)
        if item["title"]:
            out.append(item)
    return out


def pdf_filename(member_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", _plain(member_name)).strip("-") or "member"
    return f"AYUN-sports-performance-{slug}.pdf"


def build_member_report(record: Any) -> dict[str, Any]:
    published = record.published or {}
    confirmed = bool(published)
    assessment = record.assessment or {}
    if confirmed:
        recommendations = _active(published.get("recommendations"))
        protocols: list[dict[str, Any]] = []
        note = _plain(published.get("clinician_note"))
        when = published.get("published_at") or record.created_at or ""
        confirmed_by = _plain(published.get("published_by"))
    else:
        recommendations = _active(assessment.get("triggered"))
        ratings = assessment.get("ratings") or []
        protocols = []
        for row in assessment.get("protocol_recommendations") or []:
            if not _protocol_indicated(str(row.get("key") or ""), ratings):
                continue
            item = _recommendation(row)
            if item["title"]:
                protocols.append(item)
        note = ""
        when = record.created_at or ""
        confirmed_by = ""
    return _report(
        record,
        recommendations=recommendations,
        protocols=protocols,
        confirmed=confirmed,
        confirmed_by=confirmed_by,
        when=when,
        clinician_note=note,
        audience="member",
    )


def build_clinician_report(
    record: Any,
    recommendations: list[dict[str, Any]] | None = None,
    clinician_note: str | None = None,
) -> dict[str, Any]:
    published = record.published or {}
    confirmed = bool(published)
    if recommendations is None:
        source = published.get("recommendations") if confirmed else record.active_draft_recommendations()
    else:
        source = recommendations
    note = published.get("clinician_note") if clinician_note is None else clinician_note
    when = (published.get("published_at") if confirmed else "") or record.created_at or ""
    return _report(
        record,
        recommendations=_active(source),
        protocols=[],
        confirmed=confirmed,
        confirmed_by=_plain(published.get("published_by")) if confirmed else "",
        when=when,
        clinician_note=_plain(note),
        audience="clinician",
    )


def _report(
    record: Any,
    *,
    recommendations: list[dict[str, Any]],
    protocols: list[dict[str, Any]],
    confirmed: bool,
    confirmed_by: str,
    when: str,
    clinician_note: str,
    audience: str,
) -> dict[str, Any]:
    profile = record.personal_profile or {}
    name = _plain(record.member_name or profile.get("name") or "Member")
    assessment = record.assessment or {}
    known = {item["title"].lower() for item in recommendations}
    extra = [item for item in protocols if item["title"].lower() not in known]
    ratings = []
    for row in assessment.get("ratings") or []:
        if row.get("value") is None:
            continue
        parameter = _plain(row.get("parameter"))
        ratings.append({
            "name": parameter.split("::")[-1] or parameter,
            "value": _plain(row.get("value")),
            "unit": _plain(row.get("unit")),
            "rating": _RATING_LABELS.get(str(row.get("rating") or "").lower(), _plain(row.get("rating")).replace("_", " ")),
        })
    zones = assessment.get("training_zones") or None
    return {
        "member_name": name,
        "age": _age(record.member_data or {}),
        "sex": _plain((record.member_data or {}).get("Demographic::Sex")),
        "date": _fmt_date(when),
        "goal": _goals(profile),
        "confirmed": confirmed,
        "confirmed_by": confirmed_by,
        "clinician_note": clinician_note,
        "audience": audience,
        "recommendations": recommendations,
        "protocols": extra,
        "ratings": ratings,
        "zones": zones if isinstance(zones, dict) else None,
    }


def sports_performance_pdf(report: dict[str, Any]) -> bytes:
    doc = _Pdf()
    doc.start_page(cover=True)
    _draw_cover(doc, report)
    doc.start_page()
    _draw_body(doc, report)
    return doc.finish()


class _Pdf:
    def __init__(self) -> None:
        self.buf = BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.width, self.height = A4
        self.page = 0
        self.y = 0.0
        self.cover = False
        self.margin = 48.0

    def start_page(self, cover: bool = False) -> None:
        if self.page:
            self._footer()
            self.c.showPage()
        self.page += 1
        self.cover = cover
        _watermark(self.c, self.width, self.height)
        if cover:
            self.y = self.height - 48
        else:
            _draw_running_header(self.c, self.width, self.height)
            self.y = self.height - 102

    def ensure(self, height: float) -> None:
        if self.y - height < 58:
            self.start_page()

    def finish(self) -> bytes:
        self._footer()
        self.c.save()
        self.buf.seek(0)
        return self.buf.read()

    def _footer(self) -> None:
        if self.cover:
            return
        c = self.c
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(self.margin, 40, self.width - self.margin, 40)
        c.setFillColor(SOFT)
        c.setFont("Helvetica", 8)
        c.drawString(self.margin, 26, "AYUN  ·  Sports performance protocol")
        c.drawRightString(self.width - self.margin, 26, str(self.page - 1))


def _watermark(c: canvas.Canvas, width: float, height: float) -> None:
    c.saveState()
    c.setFillColor(Color(0.173, 0.404, 0.443, alpha=0.07))
    c.translate(width / 2, height / 2)
    c.rotate(32)
    c.setFont("Helvetica-Bold", 86)
    c.drawCentredString(0, 0, "AYUN")
    c.setFont("Helvetica", 14)
    c.drawCentredString(0, -28, "SPORTS PERFORMANCE")
    c.restoreState()


def _logo(c: canvas.Canvas, x: float, y: float, width: float) -> float:
    """Draw the colour logo with its top at y. Returns the height used."""
    if not _LOGO.is_file():
        c.setFillColor(TEAL)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(x, y - 18, "AYUN")
        return 22
    image = ImageReader(str(_LOGO))
    iw, ih = image.getSize()
    height = width * ih / iw
    c.drawImage(image, x, y - height, width=width, height=height, mask="auto", preserveAspectRatio=True)
    return height


def _draw_running_header(c: canvas.Canvas, width: float, height: float) -> None:
    c.setStrokeColor(RULE)
    c.setLineWidth(0.8)
    c.line(48, height - 36, width - 48, height - 36)
    c.setFillColor(INK)
    c.setFont("Helvetica", 12)
    c.drawString(48, height - 58, "Your sports performance")
    logo_w = 92
    _logo(c, width - 48 - logo_w, height - 42, logo_w)
    c.setStrokeColor(RULE)
    c.line(48, height - 72, width - 48, height - 72)


def _draw_cover(doc: _Pdf, report: dict[str, Any]) -> None:
    c = doc.c
    width, height = doc.width, doc.height
    logo_w = 168
    logo_h = _logo(c, (width - logo_w) / 2, height - 78, logo_w)

    title_y = height - 78 - logo_h - 54
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, title_y, "Sports Performance Report")

    cx, cy, outer = width / 2, title_y - 128, 74
    c.setStrokeColor(HexColor("#edf2f3"))
    c.setLineWidth(18)
    c.circle(cx, cy, outer, stroke=1, fill=0)
    c.setLineCap(1)
    c.setStrokeColor(HexColor("#3a88c8"))
    c.setLineWidth(14)
    c.arc(cx - outer, cy - outer, cx + outer, cy + outer, 125, 210)
    inner = 56
    c.setStrokeColor(HexColor("#7ddea6"))
    c.setLineWidth(12)
    c.arc(cx - inner, cy - inner, cx + inner, cy + inner, 300, 200)
    c.setStrokeColor(GREEN)
    c.setLineWidth(11)
    c.arc(cx - inner, cy - inner, cx + inner, cy + inner, 40, 150)

    c.setFillColor(SOFT)
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx, cy + 8, "Your sports")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(cx, cy - 10, "performance")

    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, cy - outer - 42, f"Sports performance check-up  |  {report['date']}")

    who = report["member_name"]
    if report["age"]:
        who = f"{who}, {report['age']}"
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(width / 2, cy - outer - 66, who)

    quote_top = cy - outer - 118
    c.setFillColor(HexColor("#c5cdc8"))
    c.setFont("Times-Bold", 42)
    c.drawCentredString(width / 2, quote_top, "\u201c")
    lines = _wrap(report["goal"], "Helvetica-Oblique", 10, width - 140)[:6]
    c.setFillColor(SOFT)
    c.setFont("Helvetica-Oblique", 10)
    y = quote_top - 28
    for line in lines:
        c.drawCentredString(width / 2, y, line)
        y -= 14

    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(72, 64, width - 72, 64)
    c.setFillColor(TEAL_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(width / 2, 44, f"{report['member_name']}   |   Your sports performance goal")


def _draw_body(doc: _Pdf, report: dict[str, Any]) -> None:
    content_w = doc.width - doc.margin * 2
    if report["audience"] == "clinician" and report["confirmed"]:
        lede = (
            f"Clinician copy. This sports performance protocol was confirmed"
            f"{(' by ' + report['confirmed_by']) if report['confirmed_by'] else ''} on {report['date']}."
        )
    elif report["audience"] == "clinician":
        lede = (
            "Clinician copy prepared for confirmation. Publish the plan for the member "
            "to receive this sports performance protocol."
        )
    elif report["confirmed"]:
        lede = (
            f"Confirmed by the AYUN clinician team"
            f"{(' (' + report['confirmed_by'] + ')') if report['confirmed_by'] else ''} on {report['date']}. "
            "This is the sports performance protocol to follow."
        )
    else:
        lede = (
            "Preliminary sports performance protocol from your profile. "
            "An AYUN clinician can confirm an updated version."
        )
    _paragraph(doc, lede, "Helvetica", 10, MUTED, 14)
    if report["clinician_note"]:
        doc.y -= 8
        _paragraph(doc, f"Clinician note. {report['clinician_note']}", "Helvetica-Oblique", 10, TEAL_DARK, 14)

    _section(doc, "Your protocol" if report["recommendations"] else "Protocol")
    if report["recommendations"]:
        for item in report["recommendations"]:
            _protocol_card(doc, item, content_w)
    else:
        _paragraph(doc, "No protocol items are included in this version.", "Helvetica", 10, MUTED, 14)

    if report["protocols"]:
        _section(doc, "Matched AYUN protocols")
        for item in report["protocols"]:
            _protocol_card(doc, item, content_w)

    zones = report.get("zones") or {}
    zone_map = zones.get("zones") if isinstance(zones, dict) else None
    if zone_map:
        _section(doc, "Training zones")
        source = _plain(zones.get("source"))
        hr = zones.get("hr_max")
        detail = source
        if hr:
            detail = f"{detail}  ·  HR max {hr} bpm".strip(" ·")
        if detail:
            _paragraph(doc, detail, "Helvetica", 9, SOFT, 12)
            doc.y -= 6
        for name, value in zone_map.items():
            _kv_row(doc, _plain(name), _plain(value), content_w)

    if report["ratings"]:
        _section(doc, "Sports check-up snapshot")
        _paragraph(
            doc,
            "Ratings use the AYUN standard, which is set higher than general health norms.",
            "Helvetica",
            9,
            SOFT,
            12,
        )
        doc.y -= 6
        for row in report["ratings"]:
            value = f"{row['value']} {row['unit']}".strip()
            if row["rating"]:
                value = f"{value}  ·  {row['rating']}"
            _kv_row(doc, row["name"], value, content_w)


def _section(doc: _Pdf, title: str) -> None:
    doc.ensure(36)
    doc.y -= 18
    doc.c.setFillColor(TEAL)
    doc.c.setFont("Helvetica-Bold", 14)
    doc.c.drawString(doc.margin, doc.y, _latin(title))
    doc.y -= 8
    doc.c.setStrokeColor(WASH)
    doc.c.setLineWidth(2)
    doc.c.line(doc.margin, doc.y, doc.margin + 42, doc.y)
    doc.y -= 16


def _paragraph(doc: _Pdf, text: str, font: str, size: float, color: Color, leading: float) -> None:
    width = doc.width - doc.margin * 2
    for line in _wrap(text, font, size, width) or [""]:
        doc.ensure(leading)
        doc.c.setFillColor(color)
        doc.c.setFont(font, size)
        doc.c.drawString(doc.margin, doc.y, line)
        doc.y -= leading


def _protocol_card(doc: _Pdf, item: dict[str, Any], width: float) -> None:
    rows = _layout_rows(item["action_items"])
    if item["description"] and not rows:
        rows = [("Focus", item["description"])]
    elif item["description"]:
        rows = [("Focus", item["description"]), *rows]
    for template in item["templates"]:
        summary = template["summary"] or template["title"]
        rows.append(("Template", f"{template['title']}. {summary}".strip(" .") if template["title"] else summary))
    inner_w = width - 28
    label_w = 88
    text_w = inner_w - label_w - 8
    prepared: list[tuple[str, list[str]]] = []
    for label, text in rows:
        prepared.append((label, _wrap(text, "Helvetica", 9, text_w) or [""]))
    note_lines = _wrap(f"Clinician note. {item['notes']}", "Helvetica-Oblique", 9, inner_w) if item["notes"] else []
    title_lines = _wrap(item["title"], "Helvetica-Bold", 12, inner_w) or ["Protocol"]
    block_h = 16 + (14 if item["priority"] else 0) + len(title_lines) * 15 + 2
    for _label, lines in prepared:
        block_h += len(lines) * 12 + 4
    if note_lines:
        block_h += 2 + len(note_lines) * 12
    block_h += 16
    if doc.y - block_h < 58 and block_h < doc.height - 170:
        doc.start_page()
    top = doc.y
    bottom = top - block_h
    doc.c.setFillColor(PAPER)
    doc.c.roundRect(doc.margin, bottom, width, block_h, 8, stroke=0, fill=1)
    doc.c.setFillColor(GREEN)
    doc.c.rect(doc.margin, bottom, 3.5, block_h, stroke=0, fill=1)
    y = top - 16
    if item["priority"]:
        doc.c.setFillColor(GREEN)
        doc.c.setFont("Helvetica-Bold", 8)
        label = item["priority"].upper()
        if item["category"]:
            label = f"{label}   ·   {item['category'].upper()}"
        doc.c.drawString(doc.margin + 16, y, _latin(label))
        y -= 14
    doc.c.setFillColor(INK)
    doc.c.setFont("Helvetica-Bold", 12)
    for line in title_lines:
        doc.c.drawString(doc.margin + 16, y, line)
        y -= 15
    y -= 2
    for label, lines in prepared:
        row_top = y
        doc.c.setFillColor(TEAL)
        doc.c.setFont("Helvetica-Bold", 8)
        doc.c.drawString(doc.margin + 16, row_top, _latin(label.upper()))
        doc.c.setFillColor(MUTED)
        doc.c.setFont("Helvetica", 9)
        for line in lines:
            doc.c.drawString(doc.margin + 16 + label_w, y, line)
            y -= 12
        y -= 4
    if note_lines:
        y -= 2
        doc.c.setFillColor(TEAL_DARK)
        doc.c.setFont("Helvetica-Oblique", 9)
        for line in note_lines:
            doc.c.drawString(doc.margin + 16, y, line)
            y -= 12
    doc.y = bottom - 12


def _kv_row(doc: _Pdf, label: str, value: str, width: float) -> None:
    value_lines = _wrap(value, "Helvetica", 9, width * 0.58) or [""]
    height = max(18, len(value_lines) * 12 + 6)
    doc.ensure(height)
    doc.c.setStrokeColor(RULE)
    doc.c.setLineWidth(0.4)
    doc.c.line(doc.margin, doc.y - height + 4, doc.margin + width, doc.y - height + 4)
    doc.c.setFillColor(TEAL_DARK)
    doc.c.setFont("Helvetica-Bold", 9)
    doc.c.drawString(doc.margin, doc.y - 10, _latin(label)[:42])
    doc.c.setFillColor(INK)
    doc.c.setFont("Helvetica", 9)
    y = doc.y - 10
    for line in value_lines:
        doc.c.drawRightString(doc.margin + width, y, line)
        y -= 12
    doc.y -= height
