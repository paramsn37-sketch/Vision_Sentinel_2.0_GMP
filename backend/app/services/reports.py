"""Shift reports as CSV and PDF (fpdf2: pure Python, no system libraries)."""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from ..db.models import IncidentRow

RULE_LABEL = {
    "intrusion": "Entered a no-entry zone",
    "overcrowding": "Zone over capacity",
    "dwell_exceeded": "Stayed too long in zone",
}


def rule_label(rule: str) -> str:
    if rule.startswith("ppe_missing:"):
        return f"Missing {rule.split(':', 1)[1]}"
    return RULE_LABEL.get(rule, rule)


def incidents_csv(rows: list[IncidentRow], camera_names: dict[str, str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "started_at", "ended_at", "duration_s", "camera", "zone", "rule", "severity", "status",
                "track_id", "peak_confidence", "reopened", "feedback"])  # fmt: skip
    for r in rows:
        w.writerow([r.id, r.started_at.isoformat(), r.ended_at.isoformat() if r.ended_at else "", r.duration_s,
                    camera_names.get(r.camera_id, r.camera_id), r.zone_name or "site-wide", rule_label(r.rule), r.severity,
                    r.status, r.track_id if r.track_id is not None else "", r.peak_conf, r.reopen_count, r.feedback or ""])  # fmt: skip
    return buf.getvalue()


class _PDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(120)
        self.cell(0, 6, f"Vision Sentinel shift report  ·  page {self.page_no()}/{{nb}}", align="C")


def shift_pdf(
    rows: list[IncidentRow], summary: dict, since: datetime, until: datetime, camera_names: dict[str, str]
) -> bytes:
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 9, "Shift safety report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(90)
    pdf.cell(
        0, 6, f"{since:%d %b %Y %H:%M} to {until:%d %b %Y %H:%M} (UTC)", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.ln(4)
    pdf.set_text_color(0)
    stats = [
        ("Unique people", summary.get("unique_people", 0)),
        ("Incidents", len(rows)),
        ("High severity", sum(r.severity == "high" for r in rows)),
        ("Still open", sum(r.status == "open" for r in rows)),
        (
            "Compliance",
            f"{summary['compliance_rate']:.0%}" if summary.get("compliance_rate") is not None else "n/a",
        ),
    ]
    w = 190 / len(stats)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(110)
    for label, _ in stats:
        pdf.cell(w, 5, label)
    pdf.ln()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0)
    for _, value in stats:
        pdf.cell(w, 8, str(value))
    pdf.ln(12)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Incidents by type", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=9)
    for rule, n in Counter(rule_label(r.rule) for r in rows).most_common():
        pdf.cell(80, 6, rule)
        pdf.cell(20, 6, str(n), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if not rows:
        pdf.cell(0, 6, "No incidents in this period.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Incident log", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    cols = [
        ("Time", 28),
        ("Camera", 34),
        ("Zone", 38),
        ("What happened", 44),
        ("Sev.", 14),
        ("Status", 22),
        ("Dur.", 10),
    ]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(235, 235, 235)
    for name, cw in cols:
        pdf.cell(cw, 6, name, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", size=8)
    for r in rows:
        cells = [
            f"{r.started_at:%d %b %H:%M:%S}", camera_names.get(r.camera_id, r.camera_id)[:22], (r.zone_name or "site-wide")[:24],
            rule_label(r.rule)[:30], r.severity, r.status, f"{r.duration_s:.0f}s",
        ]  # fmt: skip
        for (_, cw), text in zip(cols, cells, strict=True):
            pdf.cell(cw, 5.5, text)
        pdf.ln()
    return bytes(pdf.output())
