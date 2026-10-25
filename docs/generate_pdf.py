"""Generate a comprehensive PDF documentation for the Camera Inspection System."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
import datetime

OUTPUT_PATH = "docs/Camera_Inspection_System_Documentation.pdf"

# ── Colour palette ────────────────────────────────────────────────────────────
C_BLUE_DARK  = colors.HexColor("#1a3a5c")
C_BLUE_MID   = colors.HexColor("#2563a8")
C_BLUE_LIGHT = colors.HexColor("#dbeafe")
C_ACCENT     = colors.HexColor("#f97316")   # orange accent
C_GREEN      = colors.HexColor("#16a34a")
C_RED        = colors.HexColor("#dc2626")
C_YELLOW     = colors.HexColor("#ca8a04")
C_GREY_BG    = colors.HexColor("#f8fafc")
C_GREY_RULE  = colors.HexColor("#cbd5e1")
C_TEXT       = colors.HexColor("#1e293b")
C_MUTED      = colors.HexColor("#64748b")
C_WHITE      = colors.white
C_BLACK      = colors.black
C_CODE_BG    = colors.HexColor("#1e293b")
C_CODE_TEXT  = colors.HexColor("#e2e8f0")

# ── Styles ────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def make_styles():
    s = {}

    s["cover_title"] = ParagraphStyle(
        "cover_title", fontName="Helvetica-Bold", fontSize=32,
        textColor=C_WHITE, alignment=TA_CENTER, leading=40, spaceAfter=8,
    )
    s["cover_sub"] = ParagraphStyle(
        "cover_sub", fontName="Helvetica", fontSize=15,
        textColor=colors.HexColor("#bfdbfe"), alignment=TA_CENTER, leading=22,
    )
    s["cover_version"] = ParagraphStyle(
        "cover_version", fontName="Helvetica", fontSize=10,
        textColor=colors.HexColor("#93c5fd"), alignment=TA_CENTER,
    )

    s["h1"] = ParagraphStyle(
        "h1", fontName="Helvetica-Bold", fontSize=20, textColor=C_BLUE_DARK,
        spaceBefore=18, spaceAfter=6, leading=26, borderPad=0,
        borderWidth=0, leftIndent=0,
    )
    s["h2"] = ParagraphStyle(
        "h2", fontName="Helvetica-Bold", fontSize=14, textColor=C_BLUE_MID,
        spaceBefore=14, spaceAfter=4, leading=20,
    )
    s["h3"] = ParagraphStyle(
        "h3", fontName="Helvetica-BoldOblique", fontSize=11, textColor=C_BLUE_DARK,
        spaceBefore=10, spaceAfter=3, leading=16,
    )
    s["body"] = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=10, textColor=C_TEXT,
        leading=15, spaceAfter=6, alignment=TA_JUSTIFY,
    )
    s["body_bold"] = ParagraphStyle(
        "body_bold", fontName="Helvetica-Bold", fontSize=10, textColor=C_TEXT,
        leading=15, spaceAfter=4,
    )
    s["bullet"] = ParagraphStyle(
        "bullet", fontName="Helvetica", fontSize=10, textColor=C_TEXT,
        leading=15, spaceAfter=3, leftIndent=16, firstLineIndent=-10,
    )
    s["code"] = ParagraphStyle(
        "code", fontName="Courier", fontSize=8.5, textColor=C_CODE_TEXT,
        backColor=C_CODE_BG, leading=13, spaceAfter=4,
        leftIndent=6, rightIndent=6, spaceBefore=4,
        borderPad=6,
    )
    s["caption"] = ParagraphStyle(
        "caption", fontName="Helvetica-Oblique", fontSize=8.5,
        textColor=C_MUTED, alignment=TA_CENTER, spaceAfter=6,
    )
    s["toc_h1"] = ParagraphStyle(
        "toc_h1", fontName="Helvetica-Bold", fontSize=11, textColor=C_BLUE_DARK,
        leading=16, spaceAfter=2,
    )
    s["toc_h2"] = ParagraphStyle(
        "toc_h2", fontName="Helvetica", fontSize=9.5, textColor=C_TEXT,
        leading=14, leftIndent=16, spaceAfter=1,
    )
    s["note"] = ParagraphStyle(
        "note", fontName="Helvetica-Oblique", fontSize=9.5,
        textColor=colors.HexColor("#0369a1"), leading=14, spaceAfter=4,
        backColor=C_BLUE_LIGHT, leftIndent=8, rightIndent=8, borderPad=6,
    )
    s["warning"] = ParagraphStyle(
        "warning", fontName="Helvetica-Bold", fontSize=9.5,
        textColor=colors.HexColor("#7c2d12"), leading=14, spaceAfter=4,
        backColor=colors.HexColor("#fef3c7"), leftIndent=8, rightIndent=8, borderPad=6,
    )
    return s

S = make_styles()

# ── Header / Footer ───────────────────────────────────────────────────────────
def on_page(canv: canvas.Canvas, doc):
    w, h = A4
    # Header stripe
    canv.saveState()
    canv.setFillColor(C_BLUE_DARK)
    canv.rect(0, h - 1.1*cm, w, 1.1*cm, fill=1, stroke=0)
    canv.setFillColor(C_WHITE)
    canv.setFont("Helvetica-Bold", 8)
    canv.drawString(1.8*cm, h - 0.75*cm, "AUTOMATED CAMERA INSPECTION SYSTEM")
    canv.setFont("Helvetica", 8)
    canv.drawRightString(w - 1.8*cm, h - 0.75*cm, "Confidential — Internal Use Only")

    # Footer rule + text
    canv.setStrokeColor(C_GREY_RULE)
    canv.setLineWidth(0.5)
    canv.line(1.8*cm, 1.2*cm, w - 1.8*cm, 1.2*cm)
    canv.setFillColor(C_MUTED)
    canv.setFont("Helvetica", 8)
    canv.drawString(1.8*cm, 0.75*cm, f"Version 0.1.0  |  {datetime.date.today().strftime('%B %Y')}")
    canv.drawRightString(w - 1.8*cm, 0.75*cm, f"Page {doc.page}")
    canv.restoreState()


def on_cover(canv: canvas.Canvas, doc):
    """Cover page — no header/footer, full bleed background."""
    w, h = A4
    canv.saveState()
    # Background gradient-ish with two rects
    canv.setFillColor(C_BLUE_DARK)
    canv.rect(0, 0, w, h, fill=1, stroke=0)
    canv.setFillColor(C_BLUE_MID)
    canv.rect(0, 0, w, h * 0.38, fill=1, stroke=0)
    # Accent bar
    canv.setFillColor(C_ACCENT)
    canv.rect(0, h * 0.38 - 0.35*cm, w, 0.35*cm, fill=1, stroke=0)
    # Date bottom-right
    canv.setFillColor(colors.HexColor("#93c5fd"))
    canv.setFont("Helvetica", 9)
    canv.drawRightString(w - 1.8*cm, 1.0*cm,
                         f"Generated: {datetime.datetime.now().strftime('%d %B %Y')}")
    canv.restoreState()


# ── Helper builders ───────────────────────────────────────────────────────────
def rule(color=C_GREY_RULE, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=4, spaceBefore=4)


def section_rule():
    return HRFlowable(width="100%", thickness=1.5, color=C_BLUE_MID, spaceAfter=6, spaceBefore=2)


def h1(text):
    return Paragraph(text, S["h1"])


def h2(text):
    return Paragraph(text, S["h2"])


def h3(text):
    return Paragraph(text, S["h3"])


def body(text):
    return Paragraph(text, S["body"])


def bold(text):
    return Paragraph(text, S["body_bold"])


def bullet(text):
    return Paragraph(f"• {text}", S["bullet"])


def code_block(text):
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = escaped.split("\n")
    formatted = "<br/>".join(lines)
    return Paragraph(formatted, S["code"])


def note(text):
    return Paragraph(f"ℹ  {text}", S["note"])


def warning(text):
    return Paragraph(f"⚠  {text}", S["warning"])


def sp(h=0.2):
    return Spacer(1, h*cm)


def kv_table(rows, col_widths=None, header=None):
    """Styled two-column key-value table."""
    w = A4[0] - 3.6*cm
    cw = col_widths or [w * 0.32, w * 0.68]
    data = []
    if header:
        data.append(header)
    data.extend(rows)

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_BLUE_DARK if header else C_GREY_BG),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE if header else C_TEXT),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [C_WHITE, C_GREY_BG]),
        ("GRID",       (0, 0), (-1, -1), 0.4, C_GREY_RULE),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
    ]
    if header:
        style.append(("FONTNAME", (0, 1), (-1, -1), "Helvetica"))
        style.append(("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"))

    t = Table([[Paragraph(str(c), ParagraphStyle("tc", fontName="Helvetica",
               fontSize=9, leading=13, textColor=C_TEXT)) for c in row]
               for row in data], colWidths=cw)
    t.setStyle(TableStyle(style))
    return t


def full_table(data, col_widths=None):
    """Header row + data rows, full-width."""
    w = A4[0] - 3.6*cm
    n_cols = len(data[0])
    cw = col_widths or [w / n_cols] * n_cols

    styled = []
    for ri, row in enumerate(data):
        styled.append([
            Paragraph(str(c), ParagraphStyle(
                "tc", fontName="Helvetica-Bold" if ri == 0 else "Helvetica",
                fontSize=9, leading=13,
                textColor=C_WHITE if ri == 0 else C_TEXT))
            for c in row
        ])

    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_BLUE_DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_GREY_BG]),
        ("GRID",          (0, 0), (-1, -1), 0.4, C_GREY_RULE),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
    ])
    t = Table(styled, colWidths=cw)
    t.setStyle(ts)
    return t


def badge(text, bg):
    """Inline coloured badge as a one-cell table."""
    cell = Paragraph(text, ParagraphStyle(
        "badge", fontName="Helvetica-Bold", fontSize=8,
        textColor=C_WHITE, alignment=TA_CENTER))
    t = Table([[cell]], colWidths=[2.8*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("ROUNDEDCORNERS",(0, 0), (-1, -1), [3, 3, 3, 3]),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# Content builders
# ═══════════════════════════════════════════════════════════════════════════════

def build_cover():
    w, h = A4
    elems = []
    elems.append(Spacer(1, 6.5*cm))
    elems.append(Paragraph("Automated Camera", S["cover_title"]))
    elems.append(Paragraph("Inspection System", S["cover_title"]))
    elems.append(Spacer(1, 0.5*cm))
    elems.append(Paragraph("Comprehensive Technical Documentation", S["cover_sub"]))
    elems.append(Spacer(1, 0.6*cm))
    elems.append(Paragraph("End-of-Line Automotive Seat Quality Inspection", S["cover_sub"]))
    elems.append(Spacer(1, 1.8*cm))
    elems.append(Paragraph("Document Version 1.0  |  System Version v0.1.0", S["cover_version"]))
    elems.append(Spacer(1, 0.3*cm))
    elems.append(Paragraph("Confidential — Internal Use Only", S["cover_version"]))
    return elems


def build_toc():
    elems = []
    elems.append(h1("Table of Contents"))
    elems.append(section_rule())
    elems.append(sp(0.3))

    toc = [
        ("1.", "System Overview", ""),
        ("", "1.1  What is the System?", ""),
        ("", "1.2  Key Capabilities", ""),
        ("", "1.3  Technology Stack", ""),
        ("2.", "System Architecture", ""),
        ("", "2.1  High-Level Architecture", ""),
        ("", "2.2  Inspection Flow", ""),
        ("", "2.3  Core Components", ""),
        ("3.", "Shadow Mode — Complete Guide", ""),
        ("", "3.1  What is Shadow Mode?", ""),
        ("", "3.2  Normal Mode vs Shadow Mode", ""),
        ("", "3.3  Behaviour In Detail", ""),
        ("", "3.4  Configuration", ""),
        ("", "3.5  Shadow Mode Analytics", ""),
        ("", "3.6  When to Use Shadow Mode", ""),
        ("4.", "Inspection Stations", ""),
        ("", "4.1  Station 1 — Leather / Rexene Surface", ""),
        ("", "4.2  Station 2 — Stitching Quality", ""),
        ("", "4.3  Station 3 — Plastic Parts & Shield", ""),
        ("", "4.4  Station 4 — Mechanism Cycle Test", ""),
        ("5.", "Hardware Components", ""),
        ("", "5.1  Camera Adapters", ""),
        ("", "5.2  PLC Integration", ""),
        ("", "5.3  Lighting Control", ""),
        ("", "5.4  RFID & Barcode", ""),
        ("", "5.5  Conveyor & Diverter", ""),
        ("", "5.6  Operator Panel", ""),
        ("6.", "Vision & AI Pipeline", ""),
        ("", "6.1  AI Models", ""),
        ("", "6.2  Classical Vision", ""),
        ("", "6.3  Measurement & Limits", ""),
        ("7.", "Dashboard & Frontend Features", ""),
        ("8.", "REST API Reference", ""),
        ("9.", "Quality Control Features", ""),
        ("", "9.1  Human Review Queue", ""),
        ("", "9.2  Audit Sampling", ""),
        ("", "9.3  Shift Reports", ""),
        ("", "9.4  SPC Charts", ""),
        ("10.", "Configuration Reference", ""),
        ("11.", "Safety & Interlocks", ""),
        ("Appendix A.", "Feature Summary", ""),
        ("Appendix B.", "API Quick Reference", ""),
        ("Appendix C.", "Database Schema", ""),
    ]

    for num, title, _ in toc:
        if num and num.endswith(".") and not num.startswith(""):
            indent = 0
        else:
            indent = 16 if not num else 0

        if num and "." in num and len(num) > 2:
            st = S["toc_h2"]
        elif num:
            st = S["toc_h1"]
        else:
            st = S["toc_h2"]

        text = f"<b>{num}</b>  {title}" if num else f"  {title}"
        elems.append(Paragraph(text, st))

    return elems


# ── Section 1 ─────────────────────────────────────────────────────────────────
def build_section1():
    e = []
    e.append(h1("1. System Overview"))
    e.append(section_rule())
    e.append(sp(0.1))

    e.append(h2("1.1  What is the System?"))
    e.append(body(
        "The <b>Automated Camera Inspection System</b> is an end-of-line (EOL) "
        "quality inspection solution for automotive seat manufacturing. It performs "
        "automated visual inspection at four sequential stations along the production "
        "line, using a combination of machine vision algorithms and deep-learning AI "
        "models to detect cosmetic defects, verify component presence, and validate "
        "mechanism operation — all without slowing production throughput."
    ))
    e.append(body(
        "Each seat travels through four stations. Results from all stations are "
        "aggregated by the <b>Inspection Coordinator</b>, which drives a safety "
        "interlock: the OEM label printer is energised <i>only</i> when every station "
        "confirms a clean pass, the recliner mechanism cycle passes, and the lock "
        "sensor is confirmed. Any failure holds the pallet and diverts it to the "
        "reject spur."
    ))

    e.append(sp(0.2))
    e.append(h2("1.2  Key Capabilities"))

    caps = [
        ("Multi-Station Pipeline", "Four independent inspection stations covering leather surface, stitching, plastics, and full mechanism cycle."),
        ("AI-Powered Detection", "ONNX inference with PatchCore anomaly detection (Stn 1) and YOLO defect detectors (Stn 2-4)."),
        ("Shadow Mode", "Run the full pipeline in observation-only mode — no physical PLC outputs — to validate AI before go-live."),
        ("Human Review Queue", "Borderline detections enter a review queue; an inspector confirms PASS / REWORK / SCRAP."),
        ("Immutable Audit Trail", "Every decision, reviewer action, and system event is timestamped and stored in an append-only log."),
        ("Real-Time Dashboard", "Live seat-strip, quality trends, defect gallery, shift reports, SPC charts, and system health."),
        ("Shadow Mode Analytics", "Tracks AI vs inspector agreement rate, escape rate, and false-reject rate per shift."),
        ("Image Traceability", "Raw and annotated images saved per seat per camera, exportable as a ZIP audit package."),
        ("Flexible Hardware", "Camera adapters for Basler, Hikrobot, webcam, phone, RTSP; PLC adapters for Modbus, Snap7, OPC-UA."),
        ("Active Learning Pipeline", "Inspector feedback on false positives is stored as JSONL for future model retraining."),
    ]

    rows = [(f"<b>{k}</b>", v) for k, v in caps]
    e.append(kv_table(rows, header=["Capability", "Description"]))

    e.append(sp(0.3))
    e.append(h2("1.3  Technology Stack"))
    e.append(full_table([
        ["Component", "Technology"],
        ["Backend API", "Python 3.13+ / FastAPI / Uvicorn"],
        ["Database", "SQLite via SQLAlchemy ORM (PostgreSQL-ready)"],
        ["AI Inference", "ONNX Runtime — PatchCore + YOLO models"],
        ["Classical Vision", "OpenCV"],
        ["PLC Communication", "Simulator / Modbus / Snap7 / OPC-UA"],
        ["Camera SDKs", "pypylon (Basler), MVS SDK (Hikrobot), OpenCV (webcam)"],
        ["Frontend", "React + TypeScript + Vite + Recharts"],
        ["API Documentation", "Swagger UI at /docs"],
        ["Config Format", "YAML (system, stations, variants)"],
    ], col_widths=[6*cm, 10.5*cm]))

    return e


# ── Section 2 ─────────────────────────────────────────────────────────────────
def build_section2():
    e = []
    e.append(h1("2. System Architecture"))
    e.append(section_rule())

    e.append(h2("2.1  High-Level Architecture"))
    e.append(body(
        "The diagram below represents the top-level data and control flow. "
        "Physical pallets travel left-to-right through the four stations. "
        "Each station runs independently and reports to the central Coordinator."
    ))

    arch = [
        ["Component", "Role", "Interacts With"],
        ["Station 1-4", "Capture, inspect, report", "Camera, PLC, DB, Coordinator"],
        ["Inspection Coordinator", "Aggregate results, gate label printer", "All stations, PLC, DB"],
        ["Line Controller", "Conveyor, E-Stop, diverter", "Conveyor, PLC, Operator Panel"],
        ["PLC Layer", "Physical signal I/O", "Conveyor, Printer, Sensors"],
        ["Database (SQLite)", "Persist all records", "All services"],
        ["FastAPI Server", "REST API + dashboard", "Coordinator, DB, Frontend"],
        ["React Frontend", "UI — live view, reports, settings", "FastAPI"],
    ]
    e.append(full_table(arch, col_widths=[4.5*cm, 6*cm, 6*cm]))

    e.append(sp(0.3))
    e.append(h2("2.2  Inspection Flow"))
    e.append(body(
        "A single seat traversal follows this ordered sequence:"
    ))

    steps = [
        ("1", "RFID Write", "Seat ID written to RFID tag on pallet."),
        ("2", "Station Trigger", "PLC signals each station when the pallet arrives."),
        ("3", "Barcode Read", "Station reads barcode to resolve seat ID and variant."),
        ("4", "Variant Load", "Variant config and limits loaded; LimitsEvaluator constructed."),
        ("5", "Fixture Clamp", "Fixture clamps pallet; clamp sensor confirmed before capture."),
        ("6", "Lighting Apply", "Per-camera lighting profile applied and read-back verified."),
        ("7", "Image Capture", "All enabled cameras capture; any failure → FAIL immediately."),
        ("8", "AI Inference", "ONNX model runs on each captured frame."),
        ("9", "Limits Evaluate", "Measurements compared against pass/review/fail limits."),
        ("10", "DB Persist", "Result persisted BEFORE PLC is notified (fail-safe order)."),
        ("11", "PLC Notify", "Station outcome written to PLC tag (skipped in shadow mode)."),
        ("12", "Coordinator", "All-station results aggregated; printer gating evaluated."),
        ("13", "Route Pallet", "PASS → mainline + label; FAIL/REVIEW → reject spur."),
    ]
    e.append(full_table(
        [["Step", "Name", "Description"]] + steps,
        col_widths=[1.2*cm, 4*cm, 11.3*cm]
    ))

    e.append(sp(0.3))
    e.append(h2("2.3  Core Components"))

    e.append(h3("Inspection Coordinator"))
    e.append(body(
        "The <b>InspectionCoordinator</b> service (<code>coordinator/service.py</code>) "
        "is the safety-critical aggregation engine. Key responsibilities:"
    ))
    for item in [
        "Buffer partial station results in memory until all four stations report.",
        "Enforce the printer interlock: enable ONLY when all stations PASS, mechanism PASSES, and lock sensor is confirmed.",
        "Run a background watchdog thread — seats that do not complete within cycle_timeout_s are auto-finalised as FAIL.",
        "Auto-disable the printer after print_pulse_timeout_s (5 s default) to prevent spurious prints.",
        "In shadow mode, skip all PLC calls and queue every result for human audit.",
    ]:
        e.append(bullet(item))

    e.append(sp(0.15))
    e.append(h3("Line Controller"))
    e.append(body(
        "The <b>LineController</b> (<code>line/controller.py</code>) manages physical "
        "material flow. It triggers E-Stop (stops conveyor, holds all pallets, kills printer, "
        "lights red indicator), orchestrates the per-seat cycle across all four stations, "
        "and routes the pallet to the mainline or reject spur based on the aggregated outcome."
    ))

    e.append(sp(0.15))
    e.append(h3("Base Station"))
    e.append(body(
        "Every station inherits from <b>BaseStation</b> (<code>station/base_station.py</code>). "
        "This abstract class handles: hardware pre-check, PLC trigger wait, barcode parsing, "
        "multi-camera capture sequence, lighting verification, calibration enforcement, "
        "fail-safe exception handling, DB persistence, and PLC notification."
    ))

    return e


# ── Section 3 — Shadow Mode ───────────────────────────────────────────────────
def build_section3():
    e = []
    e.append(h1("3. Shadow Mode — Complete Guide"))
    e.append(section_rule())

    e.append(h2("3.1  What is Shadow Mode?"))
    e.append(body(
        "<b>Shadow Mode</b> is a production-safe validation operating mode where the "
        "full camera inspection pipeline runs — capturing images, running AI models, "
        "computing defect decisions, and storing results — but <i>no physical outputs "
        "are driven</i>. The PLC is not commanded, pallets are never held, and the "
        "label printer is never energised."
    ))
    e.append(sp(0.15))
    e.append(note(
        "Shadow mode is the recommended approach before any go-live on a new line, "
        "after a major AI model update, or when introducing a new seat variant."
    ))

    e.append(sp(0.2))
    e.append(h2("3.2  Normal Mode vs Shadow Mode"))

    compare = [
        ["Feature / Action", "Normal Mode", "Shadow Mode"],
        ["AI inference runs", "✓ Yes", "✓ Yes"],
        ["Images captured", "✓ Yes", "✓ Yes"],
        ["Database records written", "✓ Yes", "✓ Yes"],
        ["Audit log written", "✓ Yes", "✓ Yes"],
        ["Defects detected & stored", "✓ Yes", "✓ Yes"],
        ["PLC station result written", "✓ Yes", "✗ Skipped"],
        ["Pallet hold activated", "✓ Yes on FAIL", "✗ Never"],
        ["Label printer triggered", "✓ Yes on PASS", "✗ Never"],
        ["Conveyor controlled", "✓ Yes", "✗ Never"],
        ["PASS seats queued for audit", "On request", "✓ Always"],
        ["Shift report generated", "✓ Yes", "✓ Yes"],
        ["Agreement tracking", "No baseline", "✓ AI vs Inspector"],
    ]
    e.append(full_table(compare, col_widths=[7*cm, 4*cm, 4*cm]))

    e.append(sp(0.3))
    e.append(h2("3.3  Behaviour In Detail"))

    e.append(h3("Coordinator in Shadow Mode"))
    e.append(body(
        "When <code>shadow_mode=True</code> is set on the <b>InspectionCoordinator</b>, "
        "the finalize logic still fully evaluates the overall outcome and printer "
        "eligibility — it simply skips the <code>plc.set_label_printer_enable()</code> "
        "and <code>plc.hold_pallet()</code> calls. Every finalised seat is automatically "
        "queued for human review so an inspector can record their own PASS/FAIL decision."
    ))

    e.append(sp(0.1))
    e.append(h3("Station in Shadow Mode"))
    e.append(body(
        "Each station checks <code>self.shadow_mode</code> at step 11 (PLC Notify). "
        "When true, the step is entirely skipped and a log line is written: "
        "<i>\"Shadow mode active: PLC interlock skipped for outcome FAIL\"</i>. "
        "All other pipeline steps — capture, inference, DB write — execute normally."
    ))

    e.append(sp(0.1))
    e.append(code_block(
        "# Relevant code in base_station.py  (step 12)\n"
        "if not self.shadow_mode and self.plc is not None:\n"
        "    self.plc.set_station_result(\n"
        "        self.station_id, result.outcome, seat_id=result.seat_id\n"
        "    )\n"
        "else:\n"
        "    logger.info(\n"
        "        f'Shadow mode active: PLC interlock skipped '\n"
        "        f'for outcome {result.outcome}'\n"
        "    )"
    ))

    e.append(sp(0.2))
    e.append(h2("3.4  Configuration"))

    e.append(h3("Static Configuration (system.yaml)"))
    e.append(code_block(
        "system:\n"
        "  environment: production\n"
        "  shadow_mode: false       # false = normal, true = shadow\n"
        "  operating_mode: shadow   # 'shadow' or 'camera_leads_with_audit'\n"
        "  save_images: true\n"
        "  image_retention_days: 30"
    ))

    e.append(h3("Runtime Toggle (API — no restart needed)"))
    e.append(code_block(
        "# Enable shadow mode\n"
        "POST /api/v1/system/shadow-mode\n"
        'Content-Type: application/json\n\n'
        '{"enabled": true}\n\n'
        "# Disable shadow mode\n"
        '{"enabled": false}'
    ))
    e.append(body(
        "The toggle propagates immediately to the coordinator and every running "
        "station service. The change is also recorded in the audit log."
    ))

    e.append(h3("CLI Override at Startup"))
    e.append(code_block(
        "python -m camerainspection.main \\\n"
        "    --config configs/system.yaml \\\n"
        "    --plc-adapter simulator"
    ))

    e.append(sp(0.2))
    e.append(h2("3.5  Shadow Mode Analytics"))
    e.append(body(
        "While shadow mode is active, human inspectors record their own judgement "
        "via the API. The system then tracks four KPIs:"
    ))

    kpis = [
        ["KPI", "Definition", "Ideal Target"],
        ["Agreement Rate", "% of seats where AI and inspector agree", "> 95%"],
        ["Escape Rate", "AI says PASS, inspector says FAIL (missed defect)", "< 0.5%"],
        ["False Reject Rate", "AI says FAIL, inspector says PASS (over-rejection)", "< 3%"],
        ["Review Rate", "Proportion sent to human review queue", "< 5%"],
    ]
    e.append(full_table(kpis, col_widths=[4.5*cm, 8*cm, 4*cm]))

    e.append(sp(0.15))
    e.append(body(
        "All four KPIs are visible in real time on the <b>Shadow Mode Statistics</b> "
        "dashboard view (<code>GET /api/v1/dashboard/shadow-mode</code>) and in the "
        "end-of-shift report."
    ))

    e.append(sp(0.2))
    e.append(h2("3.6  When to Use Shadow Mode"))

    scenarios = [
        ["Scenario", "Recommendation"],
        ["New line commissioning", "Run shadow for ≥ 1 week before enabling outputs"],
        ["AI model update", "Shadow mode for ≥ 500 seats before switching live"],
        ["New seat variant introduction", "Shadow for full pilot batch to tune variant limits"],
        ["Post-maintenance restart", "Shadow for one shift to confirm hardware stability"],
        ["OEM audit preparation", "Run shadow in parallel to generate comparison data"],
        ["Software update deployment", "Shadow for first shift after update"],
    ]
    e.append(full_table(scenarios, col_widths=[7.5*cm, 9*cm]))

    return e


# ── Section 4 — Stations ──────────────────────────────────────────────────────
def build_section4():
    e = []
    e.append(h1("4. Inspection Stations"))
    e.append(section_rule())

    # ── Station 1 ──────────────────────────────────────────────────────────
    e.append(h2("4.1  Station 1 — Leather / Rexene Surface Inspection"))
    e.append(body(
        "Station 1 inspects dark leather and rexene upholstery panels for cosmetic "
        "surface defects. It uses a combination of dome and low-angle raking lights "
        "to reveal texture anomalies, paired with a PatchCore anomaly detection model "
        "trained exclusively on defect-free reference images."
    ))

    e.append(h3("Station Parameters"))
    e.append(kv_table([
        ["Station ID",          "STATION_1"],
        ["Purpose",             "Dark surface anomaly detection + segmentation"],
        ["Camera Resolution",   "2592 × 1944 px"],
        ["Pixel Size",          "0.18 mm/px"],
        ["Exposure",            "15 000 µs"],
        ["Lighting — Dome",     "80% intensity"],
        ["Lighting — Low-angle","60% intensity"],
        ["AI Model",            "Anomalib PatchCore (ONNX)"],
        ["Pass Threshold",      "score < 0.40"],
        ["Review Band",         "0.40 – 0.60"],
        ["Fail Threshold",      "score ≥ 0.60"],
        ["Trigger Timeout",     "5.0 s"],
    ], col_widths=[4.5*cm, 12*cm]))

    e.append(h3("Camera Views"))
    e.append(kv_table([
        ["front_cushion_backrest", "Seating face — main inspection area for scratches, cuts, pinholes."],
        ["rear_back_map_pocket",   "Rear panel — side back and map pocket area."],
    ], col_widths=[5.5*cm, 11*cm]))

    e.append(h3("Defects Detected"))
    for d in ["Scratch", "Cut / laceration", "Pinhole", "Stain / contamination",
              "Foam showthrough", "Wrinkle / puckering", "Colour deviation"]:
        e.append(bullet(d))

    # ── Station 2 ──────────────────────────────────────────────────────────
    e.append(sp(0.2))
    e.append(h2("4.2  Station 2 — Stitching Quality Inspection"))
    e.append(body(
        "Station 2 inspects the sewn seams across bolsters, headrest, and arm using "
        "high-resolution cameras at 0.08 mm/px — fine enough to resolve individual "
        "stitches. A YOLO model detects broken threads and skip stitches; rule-based "
        "measurement verifies stitch density (SPI) and seam position."
    ))

    e.append(h3("Station Parameters"))
    e.append(kv_table([
        ["Station ID",        "STATION_2"],
        ["Purpose",           "Stitch defect detection + dimensional seam measurement"],
        ["Camera Resolution", "2592 × 1944 px"],
        ["Pixel Size",        "0.08 – 0.09 mm/px  (fine pitch)"],
        ["Lighting",          "Direct 90% intensity"],
        ["AI Model",          "YOLO stitch defect (ONNX)"],
        ["Confidence Threshold", "0.50"],
        ["Trigger Timeout",   "5.0 s"],
    ], col_widths=[4.5*cm, 12*cm]))

    e.append(h3("Camera Views"))
    e.append(kv_table([
        ["left_bolster",  "Left bolster seam — main_seam ROI."],
        ["right_bolster", "Right bolster seam — main_seam ROI."],
        ["headrest",      "Headrest seam — main_seam ROI."],
        ["seam_arm",      "Robot-arm camera with configurable poses (bolster_start / bolster_end)."],
    ], col_widths=[4*cm, 12.5*cm]))

    e.append(h3("Measurements"))
    e.append(full_table([
        ["Measurement", "Nominal", "Pass Tolerance", "Fail Threshold", "Unit"],
        ["Stitches Per Inch (SPI)", "7.0", "±0.5", "±1.0+", "spi"],
        ["Seam Position Deviation", "0.0", "±1.5 mm", "> ±2.0 mm", "mm"],
        ["Stitch Pitch Delta", "0.0", "±0.5", "> ±1.0", "spi"],
        ["Thread Colour Match", "Variant BGR", "Within tolerance", "Out of range", "–"],
    ], col_widths=[4.5*cm, 2.5*cm, 3.5*cm, 3.5*cm, 2.5*cm]))

    # ── Station 3 ──────────────────────────────────────────────────────────
    e.append(sp(0.2))
    e.append(h2("4.3  Station 3 — Plastic Parts & Shield Inspection"))
    e.append(body(
        "Station 3 verifies that all plastic components (side shield, lever handle, "
        "ISOFIX covers, clips) are present, in the correct hand (LH/RH), correctly "
        "coloured, and free of cracks or short shots. A golden-image NCC comparison "
        "is used alongside the YOLO presence model."
    ))

    e.append(h3("Station Parameters"))
    e.append(kv_table([
        ["Station ID",             "STATION_3"],
        ["Purpose",                "Part presence, hand, colour, crack, short-shot detection"],
        ["Camera Resolution",      "2592 × 1944 px"],
        ["Pixel Size",             "0.18 – 0.22 mm/px"],
        ["Lighting",               "Diffuse 85 – 90%"],
        ["AI Model",               "YOLO presence (ONNX)"],
        ["Confidence Threshold",   "0.40"],
        ["Golden Match Threshold", "0.85 (NCC)"],
        ["Colour Check",           "Enabled"],
        ["Trigger Timeout",        "5.0 s"],
    ], col_widths=[4.5*cm, 12*cm]))

    e.append(h3("Camera Views"))
    e.append(kv_table([
        ["side_shield_handle_lever", "Side shield ROI + lever/handle ROI."],
        ["underside",               "Underside clips area."],
    ], col_widths=[5.5*cm, 11*cm]))

    e.append(h3("Components Verified (FRONT_LH_BLACK variant)"))
    e.append(full_table([
        ["Component", "Expected Hand", "Required", "Count"],
        ["side_shield", "LH", "Yes", "1"],
        ["handle",      "LH", "Yes", "1"],
        ["lever",       "LH", "Yes", "1"],
        ["isofix_cover", "–", "Yes", "2"],
        ["clips",       "–",  "Yes", "6"],
    ], col_widths=[4*cm, 4*cm, 3*cm, 5.5*cm]))

    # ── Station 4 ──────────────────────────────────────────────────────────
    e.append(sp(0.2))
    e.append(h2("4.4  Station 4 — Complete Seat & Mechanism Cycle Test"))
    e.append(body(
        "Station 4 performs the final full-seat cosmetic check <i>and</i> exercises "
        "the recliner and track mechanism through a full travel cycle. The lock sensor "
        "must be confirmed before the label printer can ever be enabled. This is the "
        "critical safety gate for OEM release."
    ))

    e.append(h3("Station Parameters"))
    e.append(kv_table([
        ["Station ID",            "STATION_4"],
        ["Purpose",               "Cosmetics + recliner/track mechanism cycle + lock confirmation"],
        ["Camera Resolution",     "2592 × 1944 px"],
        ["Pixel Size",            "0.15 mm/px"],
        ["Lighting",              "Ambient 100%"],
        ["AI Model",              "YOLO cosmetic defects (ONNX)"],
        ["Confidence Threshold",  "0.45"],
        ["Mechanism Full Cycle",  "Yes — full recliner travel commanded"],
        ["Sensor Poll Timeout",   "10.0 s"],
        ["Min Lock Torque",       "15.0 Nm"],
        ["Max Slip Back",         "1.0 mm"],
        ["Trigger Timeout",       "12.0 s"],
    ], col_widths=[4.5*cm, 12*cm]))

    e.append(h3("Mechanism Measurements"))
    e.append(full_table([
        ["Measurement", "Nominal", "LSL", "USL", "Unit"],
        ["Recliner Angle", "90.0", "88.0", "92.0", "deg"],
        ["Track End Position", "240.0", "238.0", "242.0", "mm"],
    ], col_widths=[5*cm, 3*cm, 3*cm, 3*cm, 2.5*cm]))

    e.append(sp(0.15))
    e.append(warning(
        "Station 4 result is required for label printer enable. A missing or FAIL result "
        "at Station 4 prevents label printing regardless of other station outcomes."
    ))

    return e


# ── Section 5 — Hardware ──────────────────────────────────────────────────────
def build_section5():
    e = []
    e.append(h1("5. Hardware Components"))
    e.append(section_rule())

    e.append(h2("5.1  Camera Adapters"))
    e.append(body(
        "The system supports eight camera adapters. The active adapter is set per "
        "camera in the station YAML and can be overridden at startup via "
        "<code>--camera-adapter</code>."
    ))
    e.append(full_table([
        ["Adapter", "Use Case", "Notes"],
        ["replay",    "Development / CI", "Loops pre-recorded PNG/JPG from a directory."],
        ["synthetic", "Unit testing",     "Generates solid-colour or pattern frames; no hardware needed."],
        ["webcam",    "Development",      "USB webcam via OpenCV; device index configurable."],
        ["phone",     "Development",      "Android phone via DroidCam PC client."],
        ["rtsp",      "Production",       "Any RTSP-capable network camera."],
        ["ip",        "Production",       "Direct IP camera HTTP stream."],
        ["basler",    "Production",       "Basler industrial cameras via pypylon SDK."],
        ["hikrobot",  "Production",       "Hikrobot / MindVision cameras via MVS SDK."],
    ], col_widths=[2.6*cm, 3.6*cm, 10.3*cm]))

    e.append(sp(0.2))
    e.append(h2("5.2  PLC Integration"))
    e.append(body(
        "A single PLC abstraction layer (<code>hardware/plc/base.py</code>) supports "
        "four physical adapters, selectable via the <code>plc.adapter</code> config key "
        "or the <code>--plc-adapter</code> CLI flag."
    ))
    e.append(full_table([
        ["Adapter",    "Protocol",   "Typical Use"],
        ["simulator",  "In-process", "Development, CI, shadow validation."],
        ["modbus",     "Modbus TCP", "Generic industrial PLCs on port 502."],
        ["snap7",      "S7 ISO",     "Siemens S7-300/400/1200/1500 series."],
        ["opcua",      "OPC-UA",     "Modern unified automation standard."],
    ], col_widths=[3*cm, 4*cm, 9.5*cm]))

    e.append(sp(0.15))
    e.append(h3("PLC Functions"))
    for f in [
        "<b>wait_for_trigger(station_id, timeout_s)</b> — block until the pallet-arrival trigger fires.",
        "<b>read_barcode(station_id)</b> — read barcode string from the PLC register.",
        "<b>set_station_result(station_id, outcome)</b> — write PASS/FAIL/REVIEW tag to PLC.",
        "<b>hold_pallet(station_id, hold)</b> — assert/de-assert the pallet hold solenoid.",
        "<b>set_label_printer_enable(enabled)</b> — pulse the printer output relay.",
        "<b>is_mechanism_locked()</b> — read recliner lock sensor (digital input).",
        "<b>simulate_arrival(station_id, barcode)</b> — simulator helper to inject a trigger.",
        "<b>is_connected()</b> — liveness check used by system health dashboard.",
    ]:
        e.append(bullet(f))

    e.append(sp(0.2))
    e.append(h2("5.3  Lighting Control"))
    e.append(body(
        "Modbus-based lighting controllers are supported via "
        "<code>hardware/lighting/modbus_lighting.py</code>. Each camera profile "
        "specifies per-channel intensity percentages; the station verifies the "
        "read-back within ±5% before capture — failing verification raises a "
        "HardwareError and fails the seat safely."
    ))
    e.append(kv_table([
        ["dome",    "Uniform overhead dome light — reduces shadowing."],
        ["low_angle", "Side / raking light — emphasises surface texture."],
        ["direct",  "Focused collimated beam — highlights stitch detail."],
        ["diffuse", "Even diffuse panel — removes glare on plastics."],
        ["ambient", "General area illumination."],
    ], col_widths=[3.5*cm, 13*cm]))

    e.append(sp(0.2))
    e.append(h2("5.4  RFID & Barcode"))
    e.append(body(
        "An RFID writer (<code>hardware/rfid/</code>) writes the seat ID to a tag on "
        "the pallet when the cycle starts. At each station a barcode scanner (or PLC "
        "register) provides the barcode string. The system resolves the "
        "<b>seat_id</b> and <b>variant_id</b> using this priority order:"
    ))
    for s in [
        "Colon separator — <code>SEAT_ID:VARIANT_ID</code>",
        "Known-variant suffix match — <code>SEAT_ID_FRONT_LH_BLACK</code>",
        "Bare variant barcode — whole barcode is a known variant ID",
        "Fallback underscore split — <code>SEAT_ID_<rest></code>",
    ]:
        e.append(bullet(s))

    e.append(sp(0.2))
    e.append(h2("5.5  Conveyor & Diverter"))
    e.append(body(
        "The <code>LineController</code> calls the conveyor adapter to physically "
        "route each pallet after the full inspection cycle completes:"
    ))
    e.append(kv_table([
        ["release_to_mainline(seat_id)", "PASS seat — released to production mainline."],
        ["divert_to_reject(seat_id)",    "FAIL or REVIEW seat — diverted to reject/rework spur."],
        ["stop()",                       "E-Stop — immediate halt of all conveyor movement."],
    ], col_widths=[6.5*cm, 10*cm]))

    e.append(sp(0.2))
    e.append(h2("5.6  Operator Panel"))
    e.append(body(
        "An operator panel with three indicator lights provides shop-floor status at a glance."
    ))
    e.append(kv_table([
        ["Green  (solid)",  "Seat PASSED — pallet released to mainline."],
        ["Red    (solid)",  "Seat FAILED or REVIEWING — pallet held on reject spur."],
        ["Amber  (solid)",  "System in standby or E-Stop just reset."],
        ["Red + Green off", "E-Stop active — line halted."],
    ], col_widths=[4*cm, 12.5*cm]))

    return e


# ── Section 6 — Vision / AI ───────────────────────────────────────────────────
def build_section6():
    e = []
    e.append(h1("6. Vision & AI Pipeline"))
    e.append(section_rule())

    e.append(h2("6.1  AI Models"))

    e.append(h3("PatchCore — Anomaly Detection (Station 1)"))
    e.append(body(
        "PatchCore is an unsupervised anomaly detection algorithm from the Anomalib "
        "library. The model is trained on defect-free reference surfaces only. At "
        "inference it returns a pixel-level anomaly map and a scalar anomaly score "
        "(0 = normal, 1 = highly anomalous). The model is exported to ONNX for "
        "cross-platform deployment."
    ))
    e.append(kv_table([
        ["Model file",         "models/station_1/patchcore.onnx"],
        ["Input",              "2592 × 1944 RGB image"],
        ["Output",             "anomaly_score (float), anomaly_map (heatmap)"],
        ["Pass",               "score < 0.40"],
        ["Review",             "0.40 ≤ score < 0.60"],
        ["Fail",               "score ≥ 0.60"],
        ["Training",           "camerainspection/training/train_anomalib.py"],
    ], col_widths=[4.5*cm, 12*cm]))

    e.append(sp(0.15))
    e.append(h3("YOLO — Object Detection (Stations 2, 3, 4)"))
    e.append(body(
        "YOLOv8-based models are exported to ONNX and run via the "
        "<code>OnnxYoloEngine</code> inference adapter. Each model is trained on "
        "a station-specific defect class set."
    ))
    e.append(full_table([
        ["Station", "Model File", "Classes"],
        ["2 — Stitch",   "models/station_2/yolo_defect.onnx",  "broken_thread, skip_stitch"],
        ["3 — Plastic",  "models/station_3/plastic_crack.onnx","part_correct, part_missing, part_wrong"],
        ["4 — Cosmetic", "models/station_4/cosmetics.onnx",    "wrinkle_puckering, foam_showthrough"],
    ], col_widths=[3.5*cm, 6.5*cm, 6.5*cm]))

    e.append(sp(0.2))
    e.append(h2("6.2  Classical Vision"))
    e.append(kv_table([
        ["Edge / Contour",      "Canny edge detection + contour analysis for dimensional measurements."],
        ["Colour Matching",     "BGR/HSV colour comparison against variant nominal thread colour."],
        ["NCC Template Match",  "Normalised Cross-Correlation golden-image match (Station 3, threshold 0.85)."],
        ["Stitch Counting",     "Horizontal projection profile analysis to count stitches per inch."],
        ["Gap Measurement",     "Distance transform on binary edge mask to measure shield gap in mm."],
    ], col_widths=[4.5*cm, 12*cm]))

    e.append(sp(0.2))
    e.append(h2("6.3  Measurement & Limits"))
    e.append(body(
        "All dimensional measurements are expressed in real-world units (mm, degrees) "
        "using the per-camera <code>pixel_size_mm</code> calibration factor. A "
        "<b>LimitsEvaluator</b> compares each measurement against the merged limits "
        "loaded from <code>default_limits.yaml</code> plus any variant-specific overrides."
    ))
    e.append(h3("Limit Types"))
    e.append(full_table([
        ["Limit Type", "Logic", "Fields"],
        ["RangeLimit",
         "≤ pass_max → PASS | pass_max < v < fail_at → REVIEW | ≥ fail_at → FAIL",
         "pass_max, fail_at"],
        ["ToleranceLimit",
         "|v − nominal| ≤ pass_tol → PASS | ≤ fail_tol → REVIEW | > fail_tol → FAIL",
         "pass_tol, fail_tol"],
        ["BooleanRule",
         "Immediate FAIL or REVIEW on any detection; optionally required",
         "fail_on_any, review_on_any, required"],
    ], col_widths=[3.5*cm, 9*cm, 4*cm]))

    e.append(sp(0.15))
    e.append(h3("Outcome Aggregation"))
    e.append(body(
        "The worst-case aggregation rule applies across all defects and cameras: "
        "<b>FAIL > REVIEW > PASS</b>. A single FAIL defect anywhere in the station "
        "produces a FAIL station result regardless of other measurements."
    ))

    return e


# ── Section 7 — Dashboard ─────────────────────────────────────────────────────
def build_section7():
    e = []
    e.append(h1("7. Dashboard & Frontend Features"))
    e.append(section_rule())
    e.append(body(
        "The React/TypeScript frontend (built with Vite) is served from the same "
        "FastAPI origin at <code>/</code>. All components authenticate using the "
        "<code>INSPECTION_API_KEY</code> bearer token."
    ))

    views = [
        ["Component (file)", "URL / Endpoint", "Description"],
        ["LiveLine.tsx",
         "/api/v1/dashboard/live",
         "Rolling 20-seat pass/fail strip. Shows seat ID, variant, outcome, label-printer status, and timestamp in real time."],
        ["LiveCompanion.tsx",
         "/api/v1/dashboard/live-companion",
         "Per-station snapshot images, defect count, cycle time, golden reference images, and variant nominal values for the latest seat."],
        ["QualityTrends.tsx",
         "/api/v1/dashboard/quality-trends",
         "Pass / Review / Fail rate gauges and a Pareto bar chart ranking defect types by frequency."],
        ["DefectGallery.tsx",
         "/api/v1/dashboard/defect-gallery",
         "Filterable gallery of all detected defects with annotated image, bounding box, confidence, measured vs nominal value."],
        ["ShiftReport.tsx",
         "/api/v1/dashboard/shift-report",
         "End-of-shift summary: total seats, defect breakdown, camera vs inspector comparison, false reject rate."],
        ["SystemHealth.tsx",
         "/api/v1/dashboard/system-health",
         "PLC connectivity, database status, operating mode (shadow vs normal), per-station online status."],
        ["ReviewQueue.tsx",
         "/api/v1/reviews/pending",
         "List of REVIEW-state seats. Inspector selects PASS / REWORK / SCRAP and adds notes."],
        ["AuditLog.tsx",
         "/api/v1/audit",
         "Paginated immutable event log filterable by seat ID."],
        ["SPCCharts.tsx",
         "/api/v1/analytics/spc-measurements",
         "X-bar control charts for all SPC metrics with UCL/LCL lines, Cpk readout, and violation count."],
        ["QualityAuditor.tsx",
         "/api/v1/audit/samples",
         "Random sampling interface for quality auditors to verify previously PASS-rated seats physically."],
        ["Settings.tsx",
         "/api/v1/system/*",
         "Toggle shadow mode, toggle image saving, trigger image cleanup, view storage statistics."],
        ["ROIEditor.tsx",
         "/api/v1/stations/{id}/rois",
         "Interactive bounding box editor to redefine Regions of Interest per camera without code changes."],
        ["StationTester.tsx",
         "/api/v1/stations/{id}/inject-image",
         "Upload any image to run it through a station's full AI + limits pipeline and see the annotated result."],
        ["LiveCameraStreams.tsx",
         "/api/v1/live-inspect-proxy",
         "Live surface analysis from a connected webcam or phone camera, showing defect overlays in near-real time."],
        ["PLCSimulator.tsx",
         "Internal",
         "Visual PLC simulator panel showing pallet positions, trigger states, and printer relay status."],
        ["MESIntegration.tsx",
         "Internal",
         "MES/ERP integration status panel for upstream production order data."],
        ["DefectTaxonomy.tsx",
         "Internal",
         "Reference panel showing the full defect taxonomy with example images and descriptions."],
    ]
    e.append(full_table(views, col_widths=[4.5*cm, 5*cm, 7*cm]))

    return e


# ── Section 8 — API ───────────────────────────────────────────────────────────
def build_section8():
    e = []
    e.append(h1("8. REST API Reference"))
    e.append(section_rule())
    e.append(body(
        "All endpoints (except <code>/health</code> and <code>/</code>) require the "
        "<code>X-API-Key</code> header or a <code>Authorization: Bearer &lt;key&gt;</code> "
        "header. The key must be ≥ 32 characters and is set via the "
        "<code>INSPECTION_API_KEY</code> environment variable. Interactive Swagger UI "
        "is available at <code>/docs</code>."
    ))

    groups = [
        ("Ingestion & Seat Query", [
            ["POST /api/v1/stations/result",       "Submit a station inspection result (rate-limited 60/min)."],
            ["GET  /api/v1/seats/{seat_id}",        "Full inspection history and outcome for a seat."],
            ["GET  /api/v1/seats/{seat_id}/export", "ZIP bundle: JSON audit trace + defect images (rate-limited 10/min)."],
        ]),
        ("Human Review Queue", [
            ["GET  /api/v1/reviews/pending",             "List inspections in REVIEW state with image paths."],
            ["POST /api/v1/reviews/{id}/decision",       "Submit PASS / REWORK / SCRAP decision."],
        ]),
        ("Audit", [
            ["GET  /api/v1/audit",                          "Query audit log; filter by seat_id, limit up to 500."],
            ["POST /api/v1/audit/sample",                   "Randomly sample N PASS seats for quality audit."],
            ["GET  /api/v1/audit/samples",                  "List all audit samples and their status."],
            ["POST /api/v1/audit/sample/{id}/decision",     "Record auditor PASS/FAIL verdict."],
        ]),
        ("Shadow Mode", [
            ["POST /api/v1/shadow-mode/decision",       "Record an inspector's shadow decision for a seat."],
            ["GET  /api/v1/dashboard/shadow-mode",       "Shadow mode statistics — agreement, escapes, false rejects."],
            ["GET  /api/v1/dashboard/shift-report",      "Full end-of-shift quality report."],
        ]),
        ("Live Monitoring Dashboards", [
            ["GET /api/v1/dashboard/live",             "Last 20 seats — pass/fail strip."],
            ["GET /api/v1/dashboard/quality-trends",   "Pass/review/fail rates + defect Pareto."],
            ["GET /api/v1/dashboard/defect-gallery",   "Defects with images; filter by station and type."],
            ["GET /api/v1/dashboard/live-companion",   "Latest seat snapshots + golden references."],
            ["GET /api/v1/dashboard/system-health",    "PLC status, operating mode, station liveness."],
        ]),
        ("Analytics", [
            ["GET /api/v1/analytics/spc-measurements", "SPC X-bar data with UCL/LCL/Cpk for all metrics."],
        ]),
        ("System Settings", [
            ["GET  /api/v1/system/settings",          "Current runtime settings + storage stats."],
            ["POST /api/v1/system/save-images",        "Toggle image saving on/off (no restart needed)."],
            ["POST /api/v1/system/shadow-mode",        "Toggle shadow mode on/off (no restart needed)."],
            ["POST /api/v1/system/cleanup-images",     "Delete captures older than retention period (dry_run supported)."],
        ]),
        ("Camera Management", [
            ["GET  /api/v1/cameras/detect",           "Detect connected cameras (webcam, Basler, Hikrobot)."],
            ["GET  /api/v1/cameras/test",              "Test a specific camera adapter and return metadata."],
            ["GET  /api/v1/cameras/snapshot",          "Capture a live JPEG frame."],
            ["GET  /api/v1/cameras/config",            "Return all station camera YAML configs."],
            ["POST /api/v1/cameras/config",            "Update a camera's adapter/settings in YAML (restart required)."],
            ["GET  /api/v1/cameras/all-status",        "All configured cameras and their enabled state."],
        ]),
        ("Station Configuration", [
            ["GET  /api/v1/stations/{id}/rois",        "Fetch ROI bounding boxes for a station / camera."],
            ["POST /api/v1/stations/{id}/rois",        "Update ROI bounding boxes in YAML config."],
            ["POST /api/v1/stations/{id}/inject-image","Inject an image and run the full inspection pipeline."],
        ]),
        ("Live Inspection", [
            ["POST /api/v1/live-inspect-frame",        "Analyse a JPEG frame via Station 1 surface analyser."],
            ["GET  /api/v1/live-inspect-proxy",        "Capture from a local camera and run Station 1 analysis."],
        ]),
        ("Defect Feedback", [
            ["POST /api/v1/defects/{id}/feedback",     "Record inspector correction for active-learning pipeline."],
        ]),
        ("Golden Images", [
            ["GET /api/v1/variants/{variant}/golden-images/{component}", "Serve golden reference image."],
        ]),
    ]

    for group_name, rows in groups:
        e.append(h3(group_name))
        e.append(full_table(
            [["Endpoint", "Description"]] + rows,
            col_widths=[8*cm, 8.5*cm]
        ))
        e.append(sp(0.1))

    return e


# ── Section 9 — QC ────────────────────────────────────────────────────────────
def build_section9():
    e = []
    e.append(h1("9. Quality Control Features"))
    e.append(section_rule())

    e.append(h2("9.1  Human Review Queue"))
    e.append(body(
        "Seats with a REVIEW outcome — where the AI is not confident enough to "
        "PASS or FAIL definitively — are placed in the human review queue. An "
        "inspector accesses the <b>ReviewQueue</b> dashboard panel, views the "
        "annotated image, and submits one of three verdicts:"
    ))
    e.append(kv_table([
        ["PASS",   "Defect is within acceptable limits — pallet released to mainline."],
        ["REWORK", "Defect is present but can be corrected — pallet diverted for rework."],
        ["SCRAP",  "Seat is non-conforming and cannot be reworked — pallet scrapped."],
    ], col_widths=[2.5*cm, 14*cm]))

    e.append(sp(0.15))
    e.append(body(
        "The decision is persisted in <code>HumanReviewRecord</code> and propagated "
        "to the overall seat record. The PLC is updated and the label printer is "
        "enabled/disabled accordingly. All review actions are written to the audit log."
    ))

    e.append(sp(0.2))
    e.append(h2("9.2  Audit Sampling"))
    e.append(body(
        "A quality manager can request a random sample of PASS-rated seats for "
        "physical verification against a reference master. The system:"
    ))
    for s in [
        "Selects N seats from all PASS-state seats not previously sampled.",
        "Creates AuditSampleRecord entries with status PENDING.",
        "Lists them in the QualityAuditor dashboard.",
        "Records the auditor's PASS/FAIL verdict + discrepancy details.",
        "Writes all outcomes to the audit log.",
    ]:
        e.append(bullet(s))

    e.append(sp(0.2))
    e.append(h2("9.3  Shift Reports"))
    e.append(body(
        "The shift report (<code>GET /api/v1/dashboard/shift-report</code>) is "
        "generated on demand. It includes:"
    ))
    for s in [
        "Total seats inspected in the current data set.",
        "Pass / Review / Fail counts and percentage rates.",
        "Camera vs inspector agreement rate (shadow mode data).",
        "Defect escape rate — seats where AI passed but inspector failed.",
        "False reject rate — seats where AI failed but inspector passed.",
        "Defect type breakdown — counts per defect class.",
        "Configurable false-reject threshold for alerting (default 3%).",
    ]:
        e.append(bullet(s))

    e.append(sp(0.2))
    e.append(h2("9.4  SPC Charts"))
    e.append(body(
        "Statistical Process Control is available for seven continuous measurements "
        "across the four stations. Data is retrieved from "
        "<code>GET /api/v1/analytics/spc-measurements?metric=&lt;key&gt;</code>."
    ))
    e.append(full_table([
        ["Metric Key", "Label", "Station", "Nominal", "LSL", "USL", "Unit"],
        ["stitches_per_inch",  "SPI",                  "2", "7.0",  "6.5",  "7.5",  "spi"],
        ["stitch_spi_delta",   "Stitch Pitch Dev.",     "2", "0.0",  "−0.5", "+0.5", "spi"],
        ["seam_position_mm",   "Seam Position Dev.",    "2", "0.0",  "−1.5", "+1.5", "mm"],
        ["shield_gap_mm",      "Plastic Shield Gap",    "3", "2.5",  "0.5",  "4.5",  "mm"],
        ["flash_mm",           "Plastic Flash",         "3", "0.0",  "0.0",  "0.5",  "mm"],
        ["recliner_angle_deg", "Recliner Angle",        "4", "90.0", "88.0", "92.0", "deg"],
        ["track_position_mm",  "Track End Position",    "4", "240",  "238",  "242",  "mm"],
    ], col_widths=[4*cm, 4*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.3*cm]))

    e.append(sp(0.15))
    e.append(body(
        "Control limits are computed as mean ± 3σ. The response also returns "
        "<b>Cp</b> (process capability) and <b>Cpk</b> (process capability index) "
        "for the selected metric. If fewer than 15 real data points exist, synthetic "
        "demo data is returned so the chart is always populated."
    ))

    return e


# ── Section 10 — Config ───────────────────────────────────────────────────────
def build_section10():
    e = []
    e.append(h1("10. Configuration Reference"))
    e.append(section_rule())

    e.append(h2("10.1  System Configuration — configs/system.yaml"))
    e.append(code_block(
        "system:\n"
        '  environment: "development"   # "development" or "production"\n'
        "  shadow_mode: false           # true = shadow, false = normal\n"
        '  operating_mode: "shadow"     # "shadow" or "camera_leads_with_audit"\n'
        "  save_images: true            # false = no raw/annotated saves to disk\n"
        "  image_retention_days: 30     # captured images older than this are deleted\n"
        "\n"
        "database:\n"
        '  url: "sqlite:///./data/inspection.db"\n'
        "  echo_sql: false\n"
        "\n"
        "plc:\n"
        '  adapter: "simulator"         # simulator / modbus / snap7 / opcua\n'
        '  host: "127.0.0.1"\n'
        "  port: 502\n"
        "  rack: 0\n"
        "  slot: 1\n"
        "  poll_interval_ms: 100\n"
        "\n"
        "storage:\n"
        '  image_dir: "storage/images"\n'
        '  raw_image_dir: "storage/images/raw"\n'
        '  annotated_image_dir: "storage/images/annotated"\n'
        '  defect_crops_dir: "storage/images/defects"\n'
        "\n"
        "coordinator:\n"
        '  expected_stations: ["STATION_1","STATION_2","STATION_3","STATION_4"]\n'
        "  cycle_timeout_s: 60.0"
    ))

    e.append(sp(0.2))
    e.append(h2("10.2  Seat Variants"))
    e.append(body(
        "Each variant lives in <code>configs/variants/&lt;VARIANT_ID&gt;/config.yaml</code>."
    ))
    e.append(full_table([
        ["Variant ID",       "Description"],
        ["FRONT_LH_BLACK",   "Front Left Hand seat — black leather/rexene (default)."],
        ["FRONT_RH_BLACK",   "Front Right Hand seat — black."],
        ["FRONT_LH_GREY",    "Front Left Hand seat — grey."],
        ["REAR_BENCH_BLACK", "Rear bench seat — black."],
    ], col_widths=[5*cm, 11.5*cm]))

    e.append(sp(0.15))
    e.append(body("A variant config defines nominals, required components, golden images path, and limit overrides:"))
    e.append(code_block(
        'variant_id: "FRONT_LH_BLACK"\n'
        "hand: LH  |  position: FRONT  |  color: BLACK\n"
        "\n"
        "nominals:\n"
        "  stitch:\n"
        "    stitches_per_inch: 6.0\n"
        "    seam_position_mm: 12.0\n"
        "    thread_color_bgr: [210, 210, 210]\n"
        "  plastic:\n"
        "    shield_gap_mm: 2.5\n"
        "  mechanism:\n"
        "    recliner_angle_deg: 90.0\n"
        "    track_end_position_mm: 240.0\n"
        "\n"
        "components:\n"
        "  side_shield: { expected_hand: LH, required: true }\n"
        "  isofix_cover: { count: 2, required: true }\n"
        "  clips:        { count: 6, required: true }\n"
        "\n"
        "golden_images_dir: golden_images\n"
        "limit_overrides: {}   # empty = default_limits.yaml applies"
    ))

    e.append(sp(0.2))
    e.append(h2("10.3  CLI Launch Options"))
    e.append(code_block(
        "python -m camerainspection.main \\\n"
        "  --host 0.0.0.0               \\\n"
        "  --port 8000                  \\\n"
        "  --config configs/system.yaml \\\n"
        "  --plc-adapter simulator      \\\n"
        "  --camera-adapter replay      \\\n"
        "  --run-worker                 # start background pallet worker"
    ))

    e.append(sp(0.2))
    e.append(h2("10.4  Environment Variables"))
    e.append(kv_table([
        ["INSPECTION_API_KEY", "Required. API key ≥ 32 chars. Must not be the default placeholder."],
        ["DATABASE_URL",       "Override SQLite path, e.g. postgresql://user:pw@host/db."],
        ["CORS_ALLOWED_ORIGINS", "Comma-separated origin list for browser API calls."],
        ["UI_INDEX_PATH",      "Override the path to frontend/dist/index.html."],
        ["IMAGE_STORAGE_ROOT", "Base path for image storage (default: storage/images)."],
    ], col_widths=[4.5*cm, 12*cm]))

    return e


# ── Section 11 — Safety ───────────────────────────────────────────────────────
def build_section11():
    e = []
    e.append(h1("11. Safety & Interlocks"))
    e.append(section_rule())

    e.append(h2("11.1  Label Printer Safety Interlock"))
    e.append(body(
        "This is the primary safety gate. The label printer relay is energised if and "
        "only if <i>all five</i> conditions are simultaneously true:"
    ))
    conds = [
        ("1", "All four stations reported a result for this seat."),
        ("2", "All four station results are PASS (no REVIEW, no FAIL)."),
        ("3", "Station 4 mechanism cycle test returned PASS."),
        ("4", "Station 4 mechanism includes a valid recliner_angle_deg measurement."),
        ("5", "The PLC lock sensor is_mechanism_locked() returns True."),
    ]
    e.append(full_table(
        [["#", "Condition"]] + conds,
        col_widths=[1.2*cm, 15.3*cm]
    ))
    e.append(sp(0.1))
    e.append(warning(
        "The printer relay is also automatically disabled when: a new seat arrives "
        "on the line, the print-pulse timeout (5 s) elapses, a FAIL/REVIEW result "
        "is received from any station, or the E-Stop is triggered."
    ))

    e.append(sp(0.2))
    e.append(h2("11.2  Emergency Stop"))
    e.append(body(
        "Triggering the E-Stop via <code>LineController.trigger_emergency_stop()</code> "
        "executes these actions atomically in order:"
    ))
    for s in [
        "Stop the conveyor immediately.",
        "Disable the label printer (PLC output cleared).",
        "Assert pallet hold at ALL four stations simultaneously.",
        "Set operator panel to Red ON / Green OFF.",
        "Log a CRITICAL-level event to the application log.",
    ]:
        e.append(bullet(s))

    e.append(sp(0.15))
    e.append(body(
        "Reset is via <code>reset_emergency_stop()</code>, which clears the flag and "
        "sets the operator panel to Amber (standby). The conveyor must be restarted "
        "manually by the operator."
    ))

    e.append(sp(0.2))
    e.append(h2("11.3  Fail-Safe Error Handling"))
    e.append(body(
        "Every potential failure is handled by defaulting to the most restrictive "
        "outcome. The principle is: <i>if in doubt, hold the pallet</i>."
    ))
    e.append(full_table([
        ["Failure Scenario", "Automatic Response"],
        ["Camera fails to connect",          "FAIL result, pallet held."],
        ["Image capture returns None",        "FAIL result, pallet held."],
        ["AI inference raises exception",     "FAIL result, pallet held."],
        ["Database write fails",              "FAIL result, pallet held, PLC notified FAIL."],
        ["Fixture clamp not confirmed",       "HardwareError → FAIL, pallet held."],
        ["Lighting read-back out of tolerance","HardwareError → FAIL, pallet held."],
        ["Calibration manager absent (strict mode)","FAIL defect added to result."],
        ["Missing station result at timeout", "Seat auto-finalised as FAIL."],
        ["PLC communication lost",            "FAIL result, pallet held (no PASS reaches PLC)."],
        ["Required measurement missing / NaN","station.incomplete_checks FAIL defect added."],
        ["Zero checks / measurements produced","station.no_checks_performed FAIL defect added."],
    ], col_widths=[7*cm, 9.5*cm]))

    e.append(sp(0.2))
    e.append(h2("11.4  DB-Before-PLC Ordering"))
    e.append(body(
        "A critical safety ordering is enforced: the database record is written and "
        "committed <i>before</i> the PLC is notified of a PASS result. If the DB write "
        "fails, the outcome is downgraded to FAIL and the PLC is notified FAIL, ensuring "
        "the physical line never acts on a result that isn't persisted."
    ))

    e.append(sp(0.2))
    e.append(h2("11.5  API Security"))
    e.append(kv_table([
        ["API Key Validation",   "All write endpoints require X-API-Key (≥ 32 chars, not default). Constant-time comparison prevents timing attacks."],
        ["Rate Limiting",        "Write endpoints: 60 req/min per IP. Export endpoints: 10 req/min per IP."],
        ["Seat ID Validation",   "Regex-enforced: [A-Za-z0-9_.:-]{1,64} — prevents injection."],
        ["Path Traversal Guard", "Export endpoint verifies image paths are inside repo root before adding to ZIP."],
        ["CORS",                 "Restricted to configured origins (default: localhost ports 8000, 5500, 5173, 3000)."],
    ], col_widths=[4.5*cm, 12*cm]))

    return e


# ── Appendices ────────────────────────────────────────────────────────────────
def build_appendices():
    e = []

    e.append(h1("Appendix A — Feature Summary"))
    e.append(section_rule())
    e.append(full_table([
        ["Feature", "Description", "Location"],
        ["Multi-Station Pipeline", "4 stations: leather, stitch, plastic, mechanism", "Stations 1–4"],
        ["Shadow Mode", "Full pipeline without physical PLC outputs", "System config / API"],
        ["PatchCore AI", "Anomaly detection for surface inspection", "Station 1 / inference/"],
        ["YOLO AI", "Object detection for defects, plastics, cosmetics", "Stations 2–4 / inference/"],
        ["Fixture Control", "Automated fixture clamp/release with confirmation", "hardware/fixture/"],
        ["Lighting Control", "Per-camera lighting profiles with read-back", "hardware/lighting/"],
        ["Human Review Queue", "Inspector PASS/REWORK/SCRAP interface", "API + ReviewQueue.tsx"],
        ["Audit Sampling", "Random PASS sampling for QA auditors", "API + QualityAuditor.tsx"],
        ["Shift Reports", "End-of-shift quality analysis with AI vs inspector", "API + ShiftReport.tsx"],
        ["SPC Charts", "X-bar control charts with Cpk for 7 metrics", "API + SPCCharts.tsx"],
        ["Live Dashboard", "20-seat strip, defect gallery, quality trends", "Frontend dashboards"],
        ["Image Export", "ZIP bundle: JSON trace + annotated images per seat", "GET /seats/{id}/export"],
        ["ROI Editor", "Interactive ROI bounding box editor", "ROIEditor.tsx"],
        ["Station Tester", "Inject image through any station pipeline", "StationTester.tsx"],
        ["Active Learning", "Inspector feedback stored for model retraining", "API + data/training_feedback/"],
        ["Variant System", "Multiple seat variants with per-variant limits", "configs/variants/"],
        ["Immutable Audit Log", "Timestamped event trail for OEM compliance", "DB / GET /audit"],
        ["Image Cleanup", "Automatic retention-based storage management", "image_cleanup.py"],
        ["Camera Detection", "Auto-detect webcam/Basler/Hikrobot cameras", "GET /cameras/detect"],
    ], col_widths=[4.5*cm, 7*cm, 5*cm]))

    e.append(PageBreak())
    e.append(h1("Appendix B — API Quick Reference"))
    e.append(section_rule())
    e.append(full_table([
        ["Method", "Endpoint", "Purpose"],
        ["GET",  "/health",                                   "Service liveness check."],
        ["GET",  "/",                                         "Serve SeatGuard React dashboard."],
        ["POST", "/api/v1/stations/result",                   "Ingest station result."],
        ["GET",  "/api/v1/seats/{id}",                        "Full seat inspection history."],
        ["GET",  "/api/v1/seats/{id}/export",                 "ZIP audit trace + images."],
        ["GET",  "/api/v1/reviews/pending",                   "Review queue."],
        ["POST", "/api/v1/reviews/{id}/decision",             "Submit review verdict."],
        ["GET",  "/api/v1/audit",                             "Audit log query."],
        ["POST", "/api/v1/audit/sample",                      "Generate audit sample."],
        ["GET",  "/api/v1/audit/samples",                     "List audit samples."],
        ["POST", "/api/v1/audit/sample/{id}/decision",        "Submit audit verdict."],
        ["POST", "/api/v1/shadow-mode/decision",              "Record shadow decision."],
        ["GET",  "/api/v1/dashboard/live",                    "Live 20-seat strip."],
        ["GET",  "/api/v1/dashboard/quality-trends",          "Pass/fail rates + Pareto."],
        ["GET",  "/api/v1/dashboard/defect-gallery",          "Filterable defect gallery."],
        ["GET",  "/api/v1/dashboard/live-companion",          "Latest seat snapshots."],
        ["GET",  "/api/v1/dashboard/shift-report",            "Shift quality report."],
        ["GET",  "/api/v1/dashboard/shadow-mode",             "Shadow mode stats."],
        ["GET",  "/api/v1/dashboard/system-health",           "System health."],
        ["GET",  "/api/v1/analytics/spc-measurements",        "SPC chart data."],
        ["GET",  "/api/v1/system/settings",                   "Runtime settings."],
        ["POST", "/api/v1/system/save-images",                "Toggle image saving."],
        ["POST", "/api/v1/system/shadow-mode",                "Toggle shadow mode."],
        ["POST", "/api/v1/system/cleanup-images",             "Cleanup old images."],
        ["GET",  "/api/v1/cameras/detect",                    "Detect cameras."],
        ["GET",  "/api/v1/cameras/test",                      "Test camera."],
        ["GET",  "/api/v1/cameras/snapshot",                  "Capture JPEG frame."],
        ["GET",  "/api/v1/cameras/config",                    "Camera YAML configs."],
        ["POST", "/api/v1/cameras/config",                    "Update camera config."],
        ["GET",  "/api/v1/stations/{id}/rois",                "Get ROI definitions."],
        ["POST", "/api/v1/stations/{id}/rois",                "Update ROI definitions."],
        ["POST", "/api/v1/stations/{id}/inject-image",        "Inject test image."],
        ["POST", "/api/v1/live-inspect-frame",                "Analyse JPEG frame."],
        ["GET",  "/api/v1/live-inspect-proxy",                "Capture + analyse live."],
        ["POST", "/api/v1/defects/{id}/feedback",             "Record defect feedback."],
    ], col_widths=[1.5*cm, 8.5*cm, 6.5*cm]))

    e.append(PageBreak())
    e.append(h1("Appendix C — Database Schema"))
    e.append(section_rule())

    tables = [
        ("SeatInspectionRecord", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment primary key."],
            ["seat_id", "String(64)", "Unique seat identifier."],
            ["variant_id", "String(64)", "Variant code, e.g. FRONT_LH_BLACK."],
            ["outcome", "String(16)", "PASS / REVIEW / FAIL."],
            ["shadow_mode", "Boolean", "Was this result produced in shadow mode?"],
            ["label_printer_enabled", "Boolean", "Was label printer enabled for this seat?"],
            ["mechanism_cycle_passed", "Boolean", "Did Station 4 mechanism cycle pass?"],
            ["lock_sensor_confirmed", "Boolean", "Was PLC lock sensor confirmed?"],
            ["created_at", "DateTime", "Timestamp when seat first arrived on line."],
            ["completed_at", "DateTime", "Timestamp when all stations reported."],
        ]),
        ("StationResultRecord", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment."],
            ["seat_id", "String(64) FK", "Links to SeatInspectionRecord."],
            ["station_id", "String(32)", "STATION_1 … STATION_4."],
            ["outcome", "String(16)", "PASS / REVIEW / FAIL."],
            ["cycle_time_ms", "Float", "Total cycle duration in milliseconds."],
            ["model_version", "String(32)", "AI model version used."],
            ["config_version", "String(32)", "Configuration version used."],
            ["raw_image_path", "String", "Relative path to primary raw image."],
            ["annotated_image_path", "String", "Relative path to annotated image."],
            ["camera_results_json", "Text", "JSON blob of per-camera results."],
            ["camera_image_paths_json", "Text", "JSON map camera_name → path."],
        ]),
        ("DefectRecord", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment."],
            ["station_result_id", "Integer FK", "Links to StationResultRecord."],
            ["defect_type", "String(64)", "Defect class name."],
            ["outcome", "String(16)", "PASS / REVIEW / FAIL."],
            ["measured_value", "Float", "Actual measured value."],
            ["nominal_value", "Float", "Target nominal value."],
            ["unit", "String(16)", "mm / deg / spi / etc."],
            ["confidence", "Float", "AI confidence score."],
            ["bbox_x/y/w/h", "Integer", "Bounding box in image pixels."],
            ["roi_name", "String", "ROI where defect was found."],
            ["camera_name", "String", "Camera that captured the defect."],
            ["description", "Text", "Human-readable defect description."],
        ]),
        ("HumanReviewRecord", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment."],
            ["seat_id", "String FK", "Seat under review."],
            ["station_id", "String", "Station that triggered the review."],
            ["inspector_id", "String", "Badge ID of reviewing inspector."],
            ["decision", "String", "PASS / REWORK / SCRAP."],
            ["notes", "Text", "Inspector notes."],
            ["status", "String", "PENDING / RESOLVED."],
            ["created_at", "DateTime", "When review was queued."],
            ["reviewed_at", "DateTime", "When inspector submitted decision."],
        ]),
        ("AuditLogRecord", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment."],
            ["seat_id", "String", "Associated seat (may be NULL for system events)."],
            ["station_id", "String", "Associated station (may be NULL)."],
            ["event_type", "String(64)", "STATION_RESULT_SUBMITTED, HUMAN_REVIEW_RESOLVED, etc."],
            ["details", "Text", "Full event details string."],
            ["timestamp", "DateTime", "UTC timestamp of event."],
        ]),
    ]

    for tname, cols in tables:
        e.append(h3(tname))
        e.append(full_table(cols, col_widths=[4*cm, 3.5*cm, 9*cm]))
        e.append(sp(0.15))

    return e


# ═══════════════════════════════════════════════════════════════════════════════
# Document assembly
# ═══════════════════════════════════════════════════════════════════════════════
def build():
    w, h = A4
    margin = 1.8*cm
    header_h = 1.1*cm
    footer_h = 1.5*cm

    doc = BaseDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin + header_h,
        bottomMargin=margin + footer_h,
        title="Automated Camera Inspection System — Technical Documentation",
        author="Camera Inspection Engineering",
    )

    cover_frame = Frame(0, 0, w, h, leftPadding=0, rightPadding=0,
                        topPadding=0, bottomPadding=0, id="cover")
    body_frame  = Frame(margin, margin + footer_h,
                        w - 2*margin, h - 2*margin - header_h - footer_h,
                        id="body")

    cover_tpl = PageTemplate(id="Cover", frames=[cover_frame], onPage=on_cover)
    body_tpl  = PageTemplate(id="Body",  frames=[body_frame],  onPage=on_page)
    doc.addPageTemplates([cover_tpl, body_tpl])

    story = []

    # 1 — Cover (cover template, then switch to body)
    story += build_cover()
    story.append(PageBreak())   # triggers template switch to Body on next page

    # 2 — Table of Contents
    story += build_toc()
    story.append(PageBreak())

    # 3 — Sections
    story += build_section1(); story.append(PageBreak())
    story += build_section2(); story.append(PageBreak())
    story += build_section3(); story.append(PageBreak())
    story += build_section4(); story.append(PageBreak())
    story += build_section5(); story.append(PageBreak())
    story += build_section6(); story.append(PageBreak())
    story += build_section7(); story.append(PageBreak())
    story += build_section8(); story.append(PageBreak())
    story += build_section9(); story.append(PageBreak())
    story += build_section10(); story.append(PageBreak())
    story += build_section11(); story.append(PageBreak())
    story += build_appendices()

    doc.build(story)
    print(f"PDF written to {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
