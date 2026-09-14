"""Shared drawing helpers for A5-planner-sized planner PDFs.

Clean / neutral design language (mirrors the web app: neutral grays, one calm
slate-indigo accent, dot-grid feel to fit a A5 planner A5 notebook).
Pure reportlab, no third-party deps beyond reportlab itself.
"""
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as _canvas

# --- palette (matches styles.css tokens) ---
INK = HexColor("#1f2430")
MUTED = HexColor("#6b7280")
LINE = HexColor("#d7dae0")
ACCENT = HexColor("#4f5d9c")
ACCENT_SOFT = HexColor("#eef0f8")
DOT = HexColor("#e3e5ea")

# category tag colors
TAGS = {
    "sort": (HexColor("#4f5d9c"), HexColor("#eef0f8")),
    "sustain": (HexColor("#3f7a5b"), HexColor("#e9f1ec")),
    "schedule": (HexColor("#7a5a86"), HexColor("#f1ecf4")),
}

# page sizes (width, height) in points
A5 = (148 * mm, 210 * mm)
A6 = (105 * mm, 148 * mm)

MARGIN = 12 * mm


class Sheet:
    """A flowing top-to-bottom layout helper over a reportlab canvas."""

    def __init__(self, c, size=A5, margin=MARGIN):
        self.c = c
        self.w, self.h = size
        self.margin = margin
        self.x = margin
        self.y = self.h - margin
        self.content_w = self.w - 2 * margin

    # --- low level ---
    def _need(self, space):
        if self.y - space < self.margin:
            self.c.showPage()
            self.y = self.h - self.margin

    def gap(self, mm_amount):
        self.y -= mm_amount * mm

    def dotgrid(self, x, y_top, w, h, step=5 * mm):
        c = self.c
        c.setFillColor(DOT)
        gx = x + step
        while gx < x + w - 1:
            gy = y_top - step
            while gy > y_top - h + 1:
                c.circle(gx, gy, 0.35, stroke=0, fill=1)
                gy -= step
            gx += step

    def ruled(self, x, y_top, w, n, step=8 * mm):
        c = self.c
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        for i in range(1, n + 1):
            yy = y_top - i * step
            c.line(x, yy, x + w, yy)
        return n * step

    # --- header ---
    def header(self, title, category=None, intro=None):
        c = self.c
        if category and category.lower() in TAGS:
            fg, bg = TAGS[category.lower()]
            label = category.upper()
            tw = c.stringWidth(label, "Helvetica-Bold", 7) + 12
            c.setFillColor(bg)
            c.roundRect(self.x, self.y - 11, tw, 13, 6, stroke=0, fill=1)
            c.setFillColor(fg)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(self.x + 6, self.y - 7, label)
            self.y -= 18
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(self.x, self.y - 14, title)
        self.y -= 20
        if intro:
            c.setFillColor(MUTED)
            self.y -= self._wrap(intro, self.x, self.y, self.content_w,
                                 "Helvetica", 8, 11)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.7)
        c.line(self.x, self.y - 4, self.x + self.content_w, self.y - 4)
        self.y -= 12

    def _wrap(self, text, x, y_top, w, font, size, leading):
        c = self.c
        c.setFont(font, size)
        words = text.split()
        line, yy, used = "", y_top, 0
        for word in words:
            trial = (line + " " + word).strip()
            if c.stringWidth(trial, font, size) > w and line:
                c.drawString(x, yy - size, line)
                yy -= leading
                used += leading
                line = word
            else:
                line = trial
        if line:
            c.drawString(x, yy - size, line)
            used += leading
        return used

    # --- elements ---
    def section(self, label):
        self._need(14 * mm)
        c = self.c
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(self.x, self.y - 9, label)
        self.y -= 16

    def label_lines(self, label, n=3, step=8 * mm):
        self._need((n + 1) * step + 6 * mm)
        c = self.c
        if label:
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(self.x, self.y - 8, label)
            self.y -= 12
        used = self.ruled(self.x, self.y, self.content_w, n, step)
        self.y -= used + 4 * mm

    def box(self, label, height_mm=40, dots=True):
        h = height_mm * mm
        self._need(h + 12 * mm)
        c = self.c
        if label:
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(self.x, self.y - 8, label)
            self.y -= 12
        top = self.y
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.roundRect(self.x, top - h, self.content_w, h, 4, stroke=1, fill=0)
        if dots:
            self.dotgrid(self.x, top, self.content_w, h)
        self.y = top - h - 5 * mm

    def checklist(self, items, two_col=False):
        c = self.c
        if not two_col:
            for it in items:
                self._need(8 * mm)
                self._checkitem(self.x, self.y, it, self.content_w)
                self.y -= 7 * mm
            self.y -= 2 * mm
            return
        col_w = (self.content_w - 6 * mm) / 2
        half = (len(items) + 1) // 2
        left, right = items[:half], items[half:]
        rows = max(len(left), len(right))
        self._need(rows * 7 * mm + 4 * mm)
        top = self.y
        yy = top
        for it in left:
            self._checkitem(self.x, yy, it, col_w)
            yy -= 7 * mm
        yy = top
        for it in right:
            self._checkitem(self.x + col_w + 6 * mm, yy, it, col_w)
            yy -= 7 * mm
        self.y = top - rows * 7 * mm - 2 * mm

    def _checkitem(self, x, y, text, w):
        c = self.c
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.7)
        c.rect(x, y - 9, 9, 9, stroke=1, fill=0)
        c.setFillColor(INK)
        # truncate to fit one line
        font, size = "Helvetica", 8
        avail = w - 14
        t = text
        while c.stringWidth(t, font, size) > avail and len(t) > 4:
            t = t[:-2]
        if t != text:
            t = t.rstrip() + "…"
        c.setFont(font, size)
        c.drawString(x + 14, y - 7, t)

    def table(self, headers, rows, row_h_mm=11, label_col=True):
        c = self.c
        n_cols = len(headers)
        cw = self.content_w / n_cols
        rh = row_h_mm * mm
        total = rh * (len(rows) + 1)
        self._need(total + 4 * mm)
        top = self.y
        # header band
        c.setFillColor(ACCENT_SOFT)
        c.rect(self.x, top - rh, self.content_w, rh, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 7.5)
        for i, htext in enumerate(headers):
            self._cell_text(htext, self.x + i * cw + 3, top - rh + 3, cw - 6, 7.5, "Helvetica-Bold")
        # grid + row labels
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        yy = top - rh
        for r, row in enumerate(rows):
            yy2 = yy - rh
            for i, val in enumerate(row):
                if i == 0 and label_col:
                    c.setFillColor(INK)
                    self._cell_text(val, self.x + 3, yy - rh + 3, cw - 6, 7.5, "Helvetica-Bold")
            yy = yy2
        # outer + inner lines
        for i in range(n_cols + 1):
            c.line(self.x + i * cw, top, self.x + i * cw, top - total)
        for r in range(len(rows) + 2):
            c.line(self.x, top - r * rh, self.x + self.content_w, top - r * rh)
        self.y = top - total - 5 * mm

    def _cell_text(self, text, x, y, w, size, font="Helvetica"):
        c = self.c
        t = text
        while c.stringWidth(t, font, size) > w and len(t) > 3:
            t = t[:-2]
        c.setFont(font, size)
        c.drawString(x, y, t)

    def quadrant(self, cells):
        """cells: list of 4 (title) strings -> 2x2 grid of labeled dotted boxes."""
        gap = 5 * mm
        cw = (self.content_w - gap) / 2
        ch = 46 * mm
        self._need(ch * 2 + gap + 4 * mm)
        top = self.y
        positions = [
            (self.x, top),
            (self.x + cw + gap, top),
            (self.x, top - ch - gap),
            (self.x + cw + gap, top - ch - gap),
        ]
        c = self.c
        for (qx, qy), title in zip(positions, cells):
            c.setStrokeColor(LINE)
            c.setLineWidth(0.6)
            c.roundRect(qx, qy - ch, cw, ch, 4, stroke=1, fill=0)
            c.setFillColor(ACCENT)
            c.setFont("Helvetica-Bold", 7.5)
            self._cell_text(title, qx + 4, qy - 10, cw - 8, 7.5, "Helvetica-Bold")
            self.dotgrid(qx, qy - 13, cw, ch - 13)
        self.y = top - ch * 2 - gap - 5 * mm

    def cards(self, n, fields, height_each_mm=None):
        for k in range(1, n + 1):
            self._need(20 * mm)
            c = self.c
            c.setFillColor(ACCENT)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(self.x, self.y - 8, f"#{k}")
            self.y -= 12
            for f in fields:
                self.label_lines(f, n=1, step=8 * mm)
            self.gap(3)


def new_canvas(path, size=A5):
    c = _canvas.Canvas(path, pagesize=size)
    c.setTitle("ADHD Planner insert")
    return c
