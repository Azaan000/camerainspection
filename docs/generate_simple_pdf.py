"""
Generate a simple, non-technical PDF explaining how the Camera Inspection System works.
Run: python -I docs/generate_simple_pdf.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import Flowable

OUTPUT = "docs/Camera_Inspection_System_Simple_Guide.pdf"

# ── Colour palette ─────────────────────────────────────────────────────────
NAVY    = HexColor("#1a2744")
BLUE    = HexColor("#1e4d8c")
LBLUE   = HexColor("#3a7bd5")
TEAL    = HexColor("#0097a7")
GREEN   = HexColor("#2e7d32")
AMBER   = HexColor("#e65100")
LGRAY   = HexColor("#f4f6f9")
MGRAY   = HexColor("#dde3ed")
DGRAY   = HexColor("#555f70")
WHITE   = white

PAGE_W, PAGE_H = A4


# ── Custom flowables ────────────────────────────────────────────────────────
class ColorBar(Flowable):
    """A full-width coloured bar (used as section header background)."""
    def __init__(self, text, color, text_color=WHITE, height=1.1*cm, font_size=14):
        super().__init__()
        self.text = text
        self.color = color
        self.text_color = text_color
        self.height = height
        self.font_size = font_size
        self.width = PAGE_W - 4*cm  # will be set properly by wrap

    def wrap(self, avail_w, avail_h):
        self.width = avail_w
        return avail_w, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(self.color)
        c.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=0)
        c.setFillColor(self.text_color)
        c.setFont("Helvetica-Bold", self.font_size)
        c.drawString(0.4*cm, 0.3*cm, self.text)


class StepBox(Flowable):
    """A numbered step card with title and body text."""
    def __init__(self, number, title, body, color=LBLUE, width=None):
        super().__init__()
        self.number = number
        self.title = title
        self.body = body
        self.color = color
        self._width = width or (PAGE_W - 4*cm)
        self.height = 2.2*cm

    def wrap(self, avail_w, avail_h):
        self._width = avail_w
        return avail_w, self.height

    def draw(self):
        c = self.canv
        w, h = self._width, self.height
        # Card background
        c.setFillColor(LGRAY)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        # Left accent bar
        c.setFillColor(self.color)
        c.roundRect(0, 0, 0.45*cm, h, 8, fill=1, stroke=0)
        c.rect(0.2*cm, 0, 0.25*cm, h, fill=1, stroke=0)
        # Number circle
        c.setFillColor(self.color)
        c.circle(1.2*cm, h/2, 0.4*cm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(1.2*cm, h/2 - 0.15*cm, str(self.number))
        # Title
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(2.0*cm, h - 0.65*cm, self.title)
        # Body
        c.setFillColor(DGRAY)
        c.setFont("Helvetica", 9.5)
        # Simple word-wrap
        words = self.body.split()
        line, lines = [], []
        for w_word in words:
            test = " ".join(line + [w_word])
            if c.stringWidth(test, "Helvetica", 9.5) < (w - 2.5*cm):
                line.append(w_word)
            else:
                lines.append(" ".join(line))
                line = [w_word]
        if line:
            lines.append(" ".join(line))
        y = h - 1.15*cm
        for ln in lines[:2]:
            c.drawString(2.0*cm, y, ln)
            y -= 0.38*cm


class InfoCard(Flowable):
    """A rounded card with an icon-like label and body."""
    def __init__(self, label, body, accent=TEAL, height=1.6*cm):
        super().__init__()
        self.label = label
        self.body = body
        self.accent = accent
        self.height = height
        self._width = PAGE_W - 4*cm

    def wrap(self, avail_w, avail_h):
        self._width = avail_w
        return avail_w, self.height

    def draw(self):
        c = self.canv
        w, h = self._width, self.height
        c.setFillColor(HexColor("#eaf4fb"))
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.roundRect(0, 0, 0.35*cm, h, 8, fill=1, stroke=0)
        c.rect(0.18*cm, 0, 0.18*cm, h, fill=1, stroke=0)
        c.setFillColor(self.accent)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(0.6*cm, h - 0.45*cm, self.label.upper())
        c.setFillColor(DGRAY)
        c.setFont("Helvetica", 9.5)
        words = self.body.split()
        line, lines = [], []
        for word in words:
            test = " ".join(line + [word])
            if c.stringWidth(test, "Helvetica", 9.5) < (w - 1.0*cm):
                line.append(word)
            else:
                lines.append(" ".join(line))
                line = [word]
        if line:
            lines.append(" ".join(line))
        y = h - 0.75*cm
        for ln in lines[:2]:
            c.drawString(0.6*cm, y, ln)
            y -= 0.38*cm


# ── Styles ──────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles["cover_title"] = ParagraphStyle(
        "cover_title", parent=base["Title"],
        fontSize=30, textColor=WHITE, leading=38,
        alignment=TA_CENTER, spaceAfter=8
    )
    styles["cover_sub"] = ParagraphStyle(
        "cover_sub", parent=base["Normal"],
        fontSize=14, textColor=MGRAY, alignment=TA_CENTER, spaceAfter=6
    )
    styles["cover_tag"] = ParagraphStyle(
        "cover_tag", parent=base["Normal"],
        fontSize=11, textColor=HexColor("#a0bce0"), alignment=TA_CENTER
    )
    styles["section_intro"] = ParagraphStyle(
        "section_intro", parent=base["Normal"],
        fontSize=11, textColor=DGRAY, leading=17,
        alignment=TA_JUSTIFY, spaceAfter=10
    )
    styles["body"] = ParagraphStyle(
        "body", parent=base["Normal"],
        fontSize=10.5, textColor=DGRAY, leading=16,
        alignment=TA_JUSTIFY, spaceAfter=8
    )
    styles["bullet"] = ParagraphStyle(
        "bullet", parent=base["Normal"],
        fontSize=10.5, textColor=DGRAY, leading=16,
        leftIndent=18, bulletIndent=4, spaceAfter=4
    )
    styles["caption"] = ParagraphStyle(
        "caption", parent=base["Normal"],
        fontSize=9, textColor=HexColor("#888"), alignment=TA_CENTER,
        spaceAfter=6
    )
    styles["h2"] = ParagraphStyle(
        "h2", parent=base["Normal"],
        fontSize=13, textColor=NAVY, fontName="Helvetica-Bold",
        spaceBefore=14, spaceAfter=6
    )
    styles["h3"] = ParagraphStyle(
        "h3", parent=base["Normal"],
        fontSize=11, textColor=BLUE, fontName="Helvetica-Bold",
        spaceBefore=10, spaceAfter=5
    )
    styles["callout"] = ParagraphStyle(
        "callout", parent=base["Normal"],
        fontSize=10, textColor=NAVY, leading=15,
        backColor=HexColor("#e8f0fb"), borderPadding=(6, 8, 6, 8),
        borderColor=LBLUE, borderWidth=0, leftIndent=6,
        spaceAfter=8
    )
    return styles


# ── Cover page ───────────────────────────────────────────────────────────────
def build_cover(story, styles):
    # Dark banner
    class CoverBanner(Flowable):
        def wrap(self, w, h): self._w = w; return w, 8*cm
        def draw(self):
            c = self.canv
            c.setFillColor(NAVY)
            c.rect(0, 0, self._w, 8*cm, fill=1, stroke=0)
            c.setFillColor(LBLUE)
            c.rect(0, 7.6*cm, self._w, 0.4*cm, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 28)
            c.drawCentredString(self._w/2, 5.5*cm, "Camera Inspection System")
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(MGRAY)
            c.drawCentredString(self._w/2, 4.7*cm, "How It Works — A Simple Guide")
            c.setFont("Helvetica", 11)
            c.setFillColor(HexColor("#8fa8cc"))
            c.drawCentredString(self._w/2, 3.9*cm, "Automated quality inspection for automotive seat manufacturing")
            # Four coloured dots representing the 4 stations
            colors = [TEAL, LBLUE, GREEN, AMBER]
            labels = ["Leather", "Stitching", "Plastic", "Mechanism"]
            start = self._w/2 - 5.5*cm
            for i, (col, lbl) in enumerate(zip(colors, labels)):
                x = start + i * 3.7*cm
                c.setFillColor(col)
                c.circle(x, 2.3*cm, 0.5*cm, fill=1, stroke=0)
                c.setFillColor(WHITE)
                c.setFont("Helvetica", 8)
                c.drawCentredString(x, 1.5*cm, lbl)

    story.append(CoverBanner())
    story.append(Spacer(1, 1.2*cm))

    # Quick-glance info table
    info_data = [
        ["Stations", "4 inspection points per seat"],
        ["Operating modes", "Normal Mode  •  Shadow (Validation) Mode"],
        ["What it checks", "Leather, Stitching, Plastic parts, Moving mechanism"],
        ["Result", "PASS  /  REVIEW  /  FAIL — recorded automatically"],
    ]
    tbl = Table(info_data, colWidths=[5*cm, 10.5*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), NAVY),
        ("BACKGROUND", (1, 0), (1, -1), LGRAY),
        ("TEXTCOLOR", (0, 0), (0, -1), WHITE),
        ("TEXTCOLOR", (1, 0), (1, -1), DGRAY),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [LGRAY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, MGRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph(
        "This guide explains the system in plain language — no technical background required.",
        styles["caption"]
    ))


# ── Section helpers ──────────────────────────────────────────────────────────
def sec(story, title, color=BLUE):
    story.append(Spacer(1, 0.3*cm))
    story.append(ColorBar(title, color))
    story.append(Spacer(1, 0.35*cm))

def h3(story, text, styles):
    story.append(Paragraph(text, styles["h3"]))

def body(story, text, styles):
    story.append(Paragraph(text, styles["body"]))

def bullets(story, items, styles):
    for item in items:
        story.append(Paragraph(f"• {item}", styles["bullet"]))

def callout(story, text, styles):
    story.append(Paragraph(text, styles["callout"]))
    story.append(Spacer(1, 0.2*cm))

def gap(story, size=0.4):
    story.append(Spacer(1, size*cm))


# ── Page 2: The Big Picture ──────────────────────────────────────────────────
def build_big_picture(story, styles):
    sec(story, "The Big Picture", NAVY)
    body(story, (
        "Every car seat that comes off the production line must be checked before it ships. "
        "Doing that check by eye — with a human inspector — is slow, tiring, and inconsistent. "
        "An inspector might catch 19 faults out of 20 in the morning but only 15 out of 20 late in the shift."
    ), styles)
    body(story, (
        "This system replaces the manual visual check with cameras and artificial intelligence. "
        "As each seat moves along the assembly line, it passes through four inspection stations. "
        "At each station, cameras take photos, and the AI analyses those photos in seconds. "
        "If a fault is found — a tear in the leather, a broken stitch, a missing plastic clip, "
        "or a jammed reclining mechanism — the system flags it immediately, before the seat leaves the factory."
    ), styles)

    gap(story)

    # Flow diagram: 4 stations in a row
    class FlowDiagram(Flowable):
        def wrap(self, w, h): self._w = w; return w, 3.5*cm
        def draw(self):
            c = self.canv
            w = self._w
            stations = [
                (TEAL,  "STATION 1", "Leather /\nRexene"),
                (LBLUE, "STATION 2", "Stitching"),
                (GREEN, "STATION 3", "Plastic\nParts"),
                (AMBER, "STATION 4", "Mechanism"),
            ]
            box_w = (w - 5*cm) / 4
            arrow_w = 5*cm / 3
            x = 0
            for i, (col, st, name) in enumerate(stations):
                # Box
                c.setFillColor(col)
                c.roundRect(x, 0.8*cm, box_w, 2.2*cm, 10, fill=1, stroke=0)
                c.setFillColor(WHITE)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(x + box_w/2, 2.4*cm, st)
                c.setFont("Helvetica", 9)
                for j, line in enumerate(name.split("\n")):
                    c.drawCentredString(x + box_w/2, 1.85*cm - j*0.35*cm, line)
                x += box_w
                # Arrow
                if i < 3:
                    mid_y = 1.9*cm
                    c.setFillColor(MGRAY)
                    # Arrow body
                    c.rect(x, mid_y - 0.1*cm, arrow_w - 0.3*cm, 0.2*cm, fill=1, stroke=0)
                    # Arrow head
                    c.setFillColor(DGRAY)
                    ax = x + arrow_w - 0.3*cm
                    path = c.beginPath()
                    path.moveTo(ax, mid_y + 0.25*cm)
                    path.lineTo(ax + 0.3*cm, mid_y)
                    path.lineTo(ax, mid_y - 0.25*cm)
                    path.close()
                    c.drawPath(path, fill=1, stroke=0)
                    x += arrow_w

            # Seat enters left, exits right
            c.setFillColor(DGRAY)
            c.setFont("Helvetica", 8)
            c.drawString(0, 0.3*cm, "← Seat enters")
            c.drawRightString(w, 0.3*cm, "Seat exits →")

    story.append(FlowDiagram())
    gap(story)

    body(story, (
        "The whole process happens automatically. The system knows when a seat has arrived "
        "(via a trigger signal from the production line), tells the cameras to take photos, "
        "runs the AI analysis, and records the result — all without any human pressing a button. "
        "A supervisor can watch everything live on a screen, and every result is saved to a database "
        "so that quality records are always available."
    ), styles)


# ── Page 3: The Four Inspection Stations ────────────────────────────────────
def build_stations(story, styles):
    sec(story, "The Four Inspection Stations", BLUE)

    body(story, (
        "Each station is responsible for a different part of the seat. "
        "They can all run at the same time — while one seat is at Station 1, "
        "a different seat can be at Station 2, and so on, keeping the line moving fast."
    ), styles)

    gap(story, 0.3)

    stations = [
        (TEAL, "Station 1 — Leather & Rexene Panel",
         "What it checks",
         "The outer covering of the seat — the leather or synthetic material (rexene) "
         "that passengers see and touch every day.",
         "Why it matters",
         "Even a small tear, scratch, crease, or uneven colour patch on the surface will "
         "be noticed by the car owner immediately. This station makes sure the visible "
         "surface is flawless before the seat moves on.",
         "How it works",
         "Two cameras photograph the front cushion and the rear backrest at the same time. "
         "Special ring and low-angle lights are switched on to make the surface texture "
         "easier to see — similar to shining a torch at a low angle across a wall to reveal bumps. "
         "The AI then compares what it sees against thousands of 'good' examples it was trained on, "
         "and highlights anything that looks out of place."),

        (LBLUE, "Station 2 — Stitching",
         "What it checks",
         "Every seam and decorative stitch line on the seat cover.",
         "Why it matters",
         "Stitching holds the cover together and gives the seat its finished look. "
         "A missed stitch, skipped seam, or crooked stitch line is both a quality and a durability issue. "
         "Catching it now is far cheaper than a warranty repair later.",
         "How it works",
         "Cameras capture high-detail images of each stitch panel. "
         "The AI has been trained to detect specific defect types such as skipped stitches, "
         "thread breaks, puckering (bunching of fabric), and stitch lines that deviate from the pattern. "
         "It can count individual stitches and measure spacing."),

        (GREEN, "Station 3 — Plastic Parts & Trim",
         "What it checks",
         "All the plastic components attached to the seat — side covers, trim panels, "
         "adjustment knobs, clips, and any buttons or controls.",
         "Why it matters",
         "Plastic parts must be present, correctly fitted, and undamaged. "
         "A missing clip might mean the trim panel falls off in service; "
         "a cracked knob is both a safety and an aesthetic issue.",
         "How it works",
         "The camera system takes images of each plastic zone. "
         "An object-detection AI (trained to recognise every part by its shape and position) "
         "checks that all required pieces are there, are the right colour, "
         "and show no cracks or chips."),

        (AMBER, "Station 4 — Seat Mechanism",
         "What it checks",
         "The moving parts of the seat — reclining, fore-aft sliding, height adjustment, "
         "and any locking mechanisms.",
         "Why it matters",
         "A seat that cannot recline properly, or that moves when it should be locked, "
         "is a safety risk. These mechanical functions must work correctly every single time.",
         "How it works",
         "The seat is moved through its range of positions while cameras watch. "
         "The AI checks that the mechanism moves smoothly, reaches the correct end positions, "
         "and locks firmly. If a part is bent, missing, or binding, "
         "the movement pattern will look wrong — and the system will flag it."),
    ]

    for col, title, l1, t1, l2, t2, l3, t3 in stations:
        story.append(KeepTogether([
            ColorBar(title, col, height=0.9*cm, font_size=11),
            Spacer(1, 0.25*cm),
        ]))
        tbl_data = [
            [Paragraph(f"<b>{l1}</b>", styles["body"]), Paragraph(t1, styles["body"])],
            [Paragraph(f"<b>{l2}</b>", styles["body"]), Paragraph(t2, styles["body"])],
            [Paragraph(f"<b>{l3}</b>", styles["body"]), Paragraph(t3, styles["body"])],
        ]
        tbl = Table(tbl_data, colWidths=[3.5*cm, 12*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), LGRAY),
            ("BACKGROUND", (1, 0), (1, -1), WHITE),
            ("TEXTCOLOR", (0, 0), (-1, -1), DGRAY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, MGRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(tbl)
        gap(story, 0.5)


# ── Page: A Seat's Journey ───────────────────────────────────────────────────
def build_journey(story, styles):
    sec(story, "A Seat's Journey Through the System", TEAL)

    body(story, (
        "Here is what happens, step by step, from the moment a seat arrives to the moment it leaves — "
        "explained as a simple sequence of events."
    ), styles)

    gap(story, 0.2)

    steps = [
        (1,  "Seat arrives at the station",
             "The production line moves the seat into position. A sensor or signal tells the system the seat has arrived.",
             TEAL),
        (2,  "Identity is confirmed",
             "A barcode or RFID tag on the seat is scanned. The system looks up which seat model and variant this is, "
             "so it knows exactly what to look for.",
             LBLUE),
        (3,  "Lights switch on, cameras ready",
             "The correct lighting for that station turns on automatically. The cameras are set up with "
             "the right settings for the seat type being inspected.",
             BLUE),
        (4,  "Photos are taken",
             "Each camera takes one or more high-resolution photographs. "
             "This happens in a fraction of a second.",
             NAVY),
        (5,  "AI analyses the images",
             "The AI model looks at every photo. It checks for defects, verifies that all parts are present, "
             "and scores how confident it is about what it found.",
             GREEN),
        (6,  "A verdict is reached",
             "Based on the scores, the system gives one of three results: "
             "PASS (all good), REVIEW (borderline — needs a human look), or FAIL (clear defect found).",
             AMBER),
        (7,  "Result is saved and displayed",
             "The verdict, the photos, and any highlighted defect areas are all saved to the database. "
             "The live dashboard updates immediately so supervisors can see the result.",
             TEAL),
        (8,  "Line signal is sent",
             "In normal mode, if the seat failed, a signal is sent to the production line control system "
             "to divert the seat for rework. In shadow mode this signal is held back (explained later).",
             LBLUE),
    ]

    for num, title, body_text, col in steps:
        story.append(StepBox(num, title, body_text, color=col))
        story.append(Spacer(1, 0.2*cm))


# ── Page: Shadow Mode ────────────────────────────────────────────────────────
def build_shadow_mode(story, styles):
    sec(story, "Shadow Mode — What It Is and Why It Exists", AMBER)

    body(story, (
        "Before any automated system is trusted to make real decisions on a production line, "
        "you need to prove it works correctly. Shadow Mode is how you do that."
    ), styles)

    gap(story, 0.2)

    # Simple analogy card
    class AnalogyCard(Flowable):
        def wrap(self, w, h): self._w = w; return w, 3.2*cm
        def draw(self):
            c = self.canv
            w = self._w
            c.setFillColor(HexColor("#fff8e1"))
            c.roundRect(0, 0, w, 3.2*cm, 10, fill=1, stroke=0)
            c.setFillColor(AMBER)
            c.roundRect(0, 0, 0.35*cm, 3.2*cm, 10, fill=1, stroke=0)
            c.rect(0.18*cm, 0, 0.18*cm, 3.2*cm, fill=1, stroke=0)
            c.setFillColor(AMBER)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(0.6*cm, 2.8*cm, "SIMPLE ANALOGY")
            c.setFillColor(NAVY)
            c.setFont("Helvetica", 10)
            lines = [
                "Think of a trainee inspector who shadows an experienced one.",
                "The trainee watches every seat, writes down their own verdict,",
                "but says nothing out loud. Afterwards, the two verdicts are compared.",
                "When the trainee's results match the experienced inspector's closely enough,",
                "the trainee is trusted to work independently.",
            ]
            y = 2.3*cm
            for line in lines:
                c.drawString(0.6*cm, y, line)
                y -= 0.38*cm

    story.append(AnalogyCard())
    gap(story, 0.4)

    h3(story, "What happens in Shadow Mode", styles)
    body(story, (
        "The cameras still take photos, the AI still analyses them, and the system still records a result. "
        "The one thing that does NOT happen is the physical output signal to the production line. "
        "No gates open, no lights flash, no seat gets diverted — the line keeps running exactly as it did before."
    ), styles)

    bullets(story, [
        "Every inspection is logged, including what the AI decided.",
        "Photos and defect highlights are saved as normal.",
        "Supervisors can review the shadow results and compare them with real human checks.",
        "If the AI is getting things wrong, it can be corrected before it has any real impact.",
    ], styles)

    gap(story, 0.3)

    h3(story, "Why this is important", styles)
    body(story, (
        "Switching directly from 'off' to 'fully in charge of the line' is too risky. "
        "Shadow Mode gives the team confidence. It lets engineers tune the AI sensitivity, "
        "verify that the cameras and lighting are working well, and build a history of results "
        "before trusting the system with live decisions."
    ), styles)

    gap(story, 0.3)

    # Mode comparison table
    h3(story, "Normal Mode vs. Shadow Mode — side by side", styles)
    comp_data = [
        ["Feature", "Normal Mode", "Shadow Mode"],
        ["Cameras take photos", "✓  Yes", "✓  Yes"],
        ["AI analyses images", "✓  Yes", "✓  Yes"],
        ["Results saved to database", "✓  Yes", "✓  Yes"],
        ["Dashboard shows results", "✓  Yes", "✓  Yes"],
        ["Signal sent to production line", "✓  Yes — seat diverted if failed", "✗  No — line is untouched"],
        ["Effect on production", "Defective seats are pulled", "Zero effect"],
        ["Typical use", "Live production", "System validation / commissioning"],
    ]
    comp_tbl = Table(comp_data, colWidths=[5.5*cm, 5.5*cm, 4.5*cm])
    comp_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -1), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGRAY]),
        ("TEXTCOLOR", (0, 1), (-1, -1), DGRAY),
        ("GRID", (0, 0), (-1, -1), 0.4, MGRAY),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(comp_tbl)


# ── Page: Results and Verdicts ───────────────────────────────────────────────
def build_verdicts(story, styles):
    sec(story, "Understanding the Results", GREEN)

    body(story, (
        "Every inspection ends with one of three verdicts. "
        "The system is designed so that a borderline case is never quietly passed or quietly failed — "
        "it is flagged for a human to review."
    ), styles)

    gap(story, 0.3)

    class VerdictCards(Flowable):
        def wrap(self, w, h): self._w = w; return w, 5.5*cm
        def draw(self):
            c = self.canv
            w = self._w
            cards = [
                (GREEN,  "PASS",   "The seat looks good.",
                         "Score is comfortably below the fault threshold.",
                         "Seat continues down the production line."),
                (AMBER,  "REVIEW", "Something looks borderline.",
                         "Score is in the uncertain middle zone.",
                         "A human inspector checks this seat before it moves on."),
                (HexColor("#c62828"), "FAIL",
                         "A clear defect was found.",
                         "Score is above the fault threshold.",
                         "Seat is diverted for rework (in normal mode)."),
            ]
            card_w = (w - 1*cm) / 3
            for i, (col, label, line1, line2, line3) in enumerate(cards):
                x = i * (card_w + 0.5*cm)
                c.setFillColor(col)
                c.roundRect(x, 0, card_w, 5.5*cm, 10, fill=1, stroke=0)
                c.setFillColor(WHITE)
                c.setFont("Helvetica-Bold", 16)
                c.drawCentredString(x + card_w/2, 4.5*cm, label)
                c.setFont("Helvetica", 9)
                for j, line in enumerate([line1, line2, line3]):
                    words = line.split()
                    ln, lns = [], []
                    for word in words:
                        test = " ".join(ln + [word])
                        if c.stringWidth(test, "Helvetica", 9) < card_w - 0.6*cm:
                            ln.append(word)
                        else:
                            lns.append(" ".join(ln)); ln = [word]
                    if ln: lns.append(" ".join(ln))
                    y0 = 3.5*cm - j*1.2*cm
                    for k, ltext in enumerate(lns[:2]):
                        c.drawCentredString(x + card_w/2, y0 - k*0.35*cm, ltext)

    story.append(VerdictCards())
    gap(story, 0.5)

    h3(story, "How the score is calculated", styles)
    body(story, (
        "The AI gives every inspection a score between 0 and 1. "
        "Think of it as a confidence level: a score near 0 means 'this looks completely normal', "
        "while a score near 1 means 'something is definitely wrong here'. "
        "Two thresholds divide the scale into three zones:"
    ), styles)
    bullets(story, [
        "Below the lower threshold → PASS",
        "Between the two thresholds → REVIEW (the 'uncertain zone')",
        "Above the upper threshold → FAIL",
    ], styles)
    body(story, (
        "The size of the uncertain zone can be adjusted per product model and even per seat variant. "
        "A luxury leather seat, for instance, might have a tighter zone than a basic fabric seat "
        "because the quality standard is higher."
    ), styles)


# ── Page: The Live Dashboard ─────────────────────────────────────────────────
def build_dashboard(story, styles):
    sec(story, "The Live Dashboard", LBLUE)

    body(story, (
        "Supervisors and quality engineers interact with the system through a web-based dashboard "
        "that runs in any browser. It shows everything in real time."
    ), styles)

    gap(story, 0.2)

    features = [
        ("Live inspection feed",
         "As each seat is inspected, the result appears on screen within seconds — "
         "verdict, station, seat ID, time, and a thumbnail of the camera image with any "
         "defect areas highlighted."),
        ("Defect heat maps",
         "When the AI finds a problem, it draws a coloured overlay on the photo showing "
         "exactly where the defect is. Green areas are fine; red or orange areas are suspect. "
         "This tells the rework team exactly where to look."),
        ("History and search",
         "Every past inspection is stored and searchable. "
         "You can look up any seat by its barcode, search by date, filter by station or verdict, "
         "and see the full photo record for any inspection ever performed."),
        ("Statistics and trends",
         "The dashboard shows charts: how many seats passed or failed today, "
         "which station is flagging the most issues, which defect type is most common. "
         "This helps the production team find root causes."),
        ("Shadow mode comparison",
         "During shadow mode, the dashboard lets engineers compare the AI's verdict "
         "with the human inspector's verdict side by side, making it easy to spot "
         "where the AI needs adjustment."),
        ("System health",
         "A status panel shows whether each camera is connected, whether the AI model is running, "
         "and whether communication with the production line is active. "
         "Any problem is immediately visible."),
    ]

    for title, desc in features:
        story.append(InfoCard(title, desc, accent=LBLUE, height=1.8*cm))
        story.append(Spacer(1, 0.2*cm))


# ── Page: Product Variants ────────────────────────────────────────────────────
def build_variants(story, styles):
    sec(story, "Handling Different Seat Models (Variants)", TEAL)

    body(story, (
        "Not every seat is the same. The factory may produce seats for different car models, "
        "in left-hand and right-hand versions, in different colours, and with different trim levels. "
        "The system handles all of these through the concept of variants."
    ), styles)

    gap(story, 0.2)

    h3(story, "What a variant is", styles)
    body(story, (
        "A variant is simply a named profile for a specific seat type. "
        "It tells the system: this seat is a front-left, black leather, sport-trim version for Model X. "
        "Each variant carries its own inspection rules — for example, a sport seat may have "
        "additional stitching patterns that a standard seat does not have."
    ), styles)

    h3(story, "How it is selected", styles)
    body(story, (
        "When the barcode or RFID tag on a seat is scanned, the system automatically loads "
        "the matching variant profile. The cameras, the AI model, and the pass/fail thresholds "
        "are all adjusted accordingly — without anyone needing to manually change any settings."
    ), styles)

    h3(story, "Why this matters", styles)
    bullets(story, [
        "The same camera station can inspect many different seat types without being reconfigured by hand.",
        "Quality standards can be set higher or lower per variant — premium variants get stricter rules.",
        "If a new seat model is added to the production line, a new variant profile is created and uploaded; "
        "the rest of the system stays the same.",
    ], styles)


# ── Page: What Happens to Images ─────────────────────────────────────────────
def build_images(story, styles):
    sec(story, "What Happens to the Images", BLUE)

    body(story, (
        "Every photo taken during an inspection is an important quality record. "
        "The system manages images carefully."
    ), styles)

    gap(story, 0.2)

    img_data = [
        ["Raw image", "The original, unmodified photo straight from the camera. "
                      "Stored as evidence exactly as captured."],
        ["Annotated image", "The same photo with coloured overlays added to show defect locations. "
                           "This is what appears on the dashboard."],
        ["Defect crop", "A zoomed-in cut of just the defect area. "
                        "Useful for rework technicians and for reporting."],
        ["Retention period", "Images are kept for a set number of days (typically 30), "
                             "then automatically deleted to manage storage space. "
                             "The inspection record in the database is kept permanently."],
    ]

    tbl = Table(img_data, colWidths=[4*cm, 11.5*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LGRAY),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("TEXTCOLOR", (1, 0), (1, -1), DGRAY),
        ("GRID", (0, 0), (-1, -1), 0.4, MGRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [WHITE, LGRAY]),
    ]))
    story.append(tbl)


# ── Page: Lighting ────────────────────────────────────────────────────────────
def build_lighting(story, styles):
    sec(story, "Why Lighting Is So Important", TEAL)

    body(story, (
        "The quality of a camera image depends almost entirely on how the subject is lit. "
        "The system uses two types of light at each station, controlled automatically."
    ), styles)

    gap(story, 0.2)

    light_data = [
        ["Dome light\n(overhead ring)",
         "Provides even, shadow-free illumination across the whole surface. "
         "Good for seeing colour variations, stains, and overall surface condition.",
         "Think of photographing a painting under museum lighting — "
         "everything is evenly lit so no detail hides in shadow."],
        ["Low-angle light\n(raking light)",
         "Shines light across the surface at a very low angle. "
         "This creates shadows behind any raised or sunken feature, making texture defects visible.",
         "Think of shining a torch sideways across a wall — "
         "every tiny bump casts a shadow and becomes easy to see."],
    ]

    for ltype, effect, analogy in light_data:
        tbl = Table(
            [[Paragraph(f"<b>{ltype}</b>", styles["body"]),
              Paragraph(effect, styles["body"]),
              Paragraph(f"<i>{analogy}</i>", styles["body"])]],
            colWidths=[3.5*cm, 7*cm, 5*cm]
        )
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), LGRAY),
            ("BACKGROUND", (1, 0), (1, 0), WHITE),
            ("BACKGROUND", (2, 0), (2, 0), HexColor("#f0f4ff")),
            ("GRID", (0, 0), (-1, -1), 0.4, MGRAY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.3*cm))

    body(story, (
        "The intensity of each light type is set per station and per camera angle. "
        "When a new seat variant is being set up, an engineer runs a test to find the "
        "best lighting combination — then that setting is saved and used automatically every time."
    ), styles)


# ── Page: How the AI Works (Simple) ──────────────────────────────────────────
def build_ai(story, styles):
    sec(story, "How the AI Decides What Is a Defect", BLUE)

    body(story, (
        "The AI is not programmed with rules like 'if you see a tear, fail the seat'. "
        "Instead, it learns from examples — the same way a human inspector learns from experience."
    ), styles)

    gap(story, 0.2)

    h3(story, "Training (the learning phase)", styles)
    body(story, (
        "Before the system is used on the production line, the AI is shown thousands of photos "
        "of good seats. It studies these and builds up a detailed 'picture in its mind' of what "
        "a normal, defect-free seat looks like from every angle. This is called training."
    ), styles)
    body(story, (
        "No defect photos are needed for this step. The AI simply learns what 'normal' looks like. "
        "Anything that deviates from normal becomes, by definition, a potential defect."
    ), styles)

    gap(story, 0.2)

    h3(story, "Inspection (the decision phase)", styles)
    body(story, (
        "When a new seat arrives, the AI compares each patch of the new photo against its memory "
        "of what that patch should look like. If a patch looks very different from any patch "
        "it has ever seen on a good seat, it is flagged as a suspect area."
    ), styles)

    gap(story, 0.2)

    h3(story, "Object detection for parts", styles)
    body(story, (
        "For stations that check whether specific parts are present (like plastic clips and trim pieces), "
        "a different AI technique is used — one that looks for specific shapes and objects in the image. "
        "This AI has been trained to recognise each part type by appearance, so it can say: "
        "'the left lower clip is missing' or 'the adjustment knob is the wrong colour'."
    ), styles)

    gap(story, 0.2)

    callout(story, (
        "Key point: the AI does not replace human judgement for borderline cases. "
        "Any result it is uncertain about is marked REVIEW so that a person can make the final call. "
        "The AI is a first-pass filter, not an infallible judge."
    ), styles)


# ── Page: Integration with the Production Line ───────────────────────────────
def build_plc(story, styles):
    sec(story, "How the System Connects to the Production Line", AMBER)

    body(story, (
        "The camera inspection system does not stand alone. "
        "It communicates with the factory's existing production control equipment."
    ), styles)

    gap(story, 0.2)

    h3(story, "What a PLC is (in plain words)", styles)
    body(story, (
        "A PLC (Programmable Logic Controller) is the brain of the production line — "
        "a rugged computer that controls all the physical machinery: conveyors, gates, lights, alarms. "
        "The inspection system talks to the PLC to receive trigger signals (seat has arrived) "
        "and to send back results (seat passed or failed)."
    ), styles)

    h3(story, "The conversation between the two systems", styles)
    conv_data = [
        ["PLC → Inspection system", "\"A seat has arrived at Station 1. Its ID is SN-20241024-0051.\""],
        ["Inspection system → PLC", "\"Seat SN-20241024-0051 has PASSED Station 1.\""],
        ["PLC → production line", "\"Let the seat continue to the next station.\""],
        ["Inspection system → PLC", "\"Seat SN-20241024-0052 has FAILED Station 2.\""],
        ["PLC → production line", "\"Divert seat SN-20241024-0052 to the rework area.\""],
    ]
    conv_tbl = Table(conv_data, colWidths=[6*cm, 9.5*cm])
    conv_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("TEXTCOLOR", (1, 0), (1, -1), DGRAY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LGRAY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.4, MGRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Oblique"),
    ]))
    story.append(conv_tbl)

    gap(story, 0.3)
    h3(story, "Simulation mode (no PLC connected)", styles)
    body(story, (
        "During development or when the physical PLC is not available, "
        "the system uses a built-in simulator. "
        "The simulator pretends to be the PLC, sending trigger signals and receiving results. "
        "This allows the entire system to be tested without any physical production line equipment."
    ), styles)


# ── Page: Summary ─────────────────────────────────────────────────────────────
def build_summary(story, styles):
    sec(story, "Summary", NAVY)

    body(story, "Here is the whole system in a handful of sentences:", styles)
    gap(story, 0.2)

    summary_points = [
        ("The goal",
         "Catch quality defects in car seats automatically, every single seat, every single shift, "
         "with consistent accuracy."),
        ("How it achieves this",
         "Four camera stations photograph different parts of each seat. "
         "AI models analyse the photos in seconds and return a PASS, REVIEW, or FAIL verdict."),
        ("Shadow Mode",
         "A safe way to validate the system before it controls the line. "
         "Everything runs as normal except the physical output signal — the line is untouched."),
        ("Normal Mode",
         "The system is trusted and connected. Failed seats are automatically diverted for rework "
         "without anyone needing to press a button."),
        ("The dashboard",
         "A live web screen gives supervisors full visibility — real-time results, photos, "
         "defect heat maps, trends, and system health."),
        ("Variants",
         "The system handles many different seat models. "
         "Scanning the barcode on each seat loads the right inspection rules automatically."),
        ("Records",
         "Every inspection, every photo, every verdict is permanently recorded. "
         "This provides a full quality history for every seat ever produced."),
    ]

    for label, text in summary_points:
        row = Table(
            [[Paragraph(f"<b>{label}</b>", styles["body"]),
              Paragraph(text, styles["body"])]],
            colWidths=[3.8*cm, 11.7*cm]
        )
        row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (0, 0), WHITE),
            ("BACKGROUND", (1, 0), (1, 0), WHITE),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LGRAY]),
            ("GRID", (0, 0), (-1, -1), 0.4, MGRAY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ]))
        story.append(row)
        story.append(Spacer(1, 0.18*cm))


# ── Page footer / header callbacks ──────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(MGRAY)
    canvas.rect(0, 0.7*cm, PAGE_W, 0.04*cm, fill=1, stroke=0)
    canvas.setFillColor(DGRAY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2*cm, 0.4*cm, "Camera Inspection System — Simple Guide")
    canvas.drawRightString(PAGE_W - 2*cm, 0.4*cm, f"Page {doc.page}")
    canvas.restoreState()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm,
        title="Camera Inspection System — Simple Guide",
        author="Camera Inspection System",
        subject="How the system works, in plain language",
    )
    styles = make_styles()
    story = []

    build_cover(story, styles)
    story.append(PageBreak())

    build_big_picture(story, styles)
    story.append(PageBreak())

    build_stations(story, styles)
    story.append(PageBreak())

    build_journey(story, styles)
    story.append(PageBreak())

    build_shadow_mode(story, styles)
    story.append(PageBreak())

    build_verdicts(story, styles)
    story.append(PageBreak())

    build_dashboard(story, styles)
    story.append(PageBreak())

    build_variants(story, styles)
    build_images(story, styles)
    story.append(PageBreak())

    build_lighting(story, styles)
    build_ai(story, styles)
    story.append(PageBreak())

    build_plc(story, styles)
    story.append(PageBreak())

    build_summary(story, styles)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF written to {OUTPUT}")


if __name__ == "__main__":
    main()
