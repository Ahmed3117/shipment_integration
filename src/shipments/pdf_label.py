import io
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import code128
from reportlab.pdfbase.pdfmetrics import stringWidth

# Arabic support
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC = True
except ImportError:
    HAS_ARABIC = False


FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_BOLD_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

ARABIC_FONT_PATH = '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'
ARABIC_FONT_BOLD_PATH = '/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf'

_fonts_registered = False


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return

    pdfmetrics.registerFont(TTFont('DejaVuBold', FONT_BOLD_PATH))

    try:
        pdfmetrics.registerFont(TTFont('NotoArabic', ARABIC_FONT_PATH))
    except:
        pass

    try:
        pdfmetrics.registerFont(TTFont('NotoArabicBold', ARABIC_FONT_BOLD_PATH))
    except:
        pass

    _fonts_registered = True


def _has_arabic(text):
    return any('\u0600' <= c <= '\u06FF' for c in str(text or ''))


def _shape_arabic(text):
    if not HAS_ARABIC or not text:
        return text or ''
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except:
        return str(text)


# ================= DRAW TEXT (ALL BOLD + BLACK) =================
def _draw_text(c, x, y, text, size=8, align='left'):
    text = str(text or '')

    if _has_arabic(text):
        text = _shape_arabic(text)
        font = 'NotoArabicBold'
    else:
        font = 'DejaVuBold'

    c.setFont(font, size)
    c.setFillColor(colors.black)

    if align == 'center':
        c.drawCentredString(x, y, text)
    elif align == 'right':
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


def _draw_multiline_text(c, x, y, text, max_width, size=8):
    text = str(text or '')

    if _has_arabic(text):
        text = _shape_arabic(text)
        font = 'NotoArabicBold'
    else:
        font = 'DejaVuBold'

    c.setFont(font, size)
    c.setFillColor(colors.black)

    def can_fit(t):
        return stringWidth(t, font, size) <= max_width

    lines = []
    current = ""

    if " " in text:
        words = text.split(" ")
        for word in words:
            test = current + (" " if current else "") + word
            if can_fit(test):
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
    else:
        chunk = ""
        for ch in text:
            test = chunk + ch
            if can_fit(test):
                chunk = test
            else:
                lines.append(chunk)
                chunk = ch
        current = chunk

    if current:
        lines.append(current)

    for i, line in enumerate(lines[:4]):
        c.drawString(x, y - (i * 4 * mm), line)


# ================= MAIN =================
def generate_shipment_label_pdf(shipment):
    _register_fonts()

    buffer = io.BytesIO()
    label_w, label_h = 105 * mm, 148 * mm
    c = canvas.Canvas(buffer, pagesize=(label_w, label_h))

    company = shipment.company
    sender = shipment.sender_address
    receiver = shipment.receiver_address

    tracking = shipment.tracking_number
    ref_number = shipment.reference_number or 'N/A'
    created_date = shipment.created_at.strftime('%Y-%m-%d') if shipment.created_at else ''

    primary_phone = getattr(receiver, 'phone', '')
    secondary_phone = getattr(receiver, 'alt_phone', '')

    dest_city = receiver.get_state_display() if receiver else 'N/A'
    origin_city = sender.get_state_display() if sender else 'N/A'

    m = 4 * mm
    w = label_w - 2 * m
    curr_y = label_h - m

    # HEADER
    header_h = 20 * mm

    _draw_text(c, m + 2*mm, curr_y - 8*mm, company.name, size=14)
    _draw_text(c, m + 2*mm, curr_y - 14*mm, f"ORIGIN: {origin_city}", size=8)

    short_dest = dest_city[:3].upper() if dest_city else ''
    _draw_text(c, label_w - m - 2*mm, curr_y - 8*mm, short_dest, size=18, align='right')
    _draw_text(c, label_w - m - 2*mm, curr_y - 14*mm, dest_city, size=8, align='right')

    curr_y -= header_h

    # BARCODE
    bc_h = 28 * mm
    c.roundRect(m, curr_y - bc_h, w, bc_h, 4, stroke=1, fill=0)

    bc = code128.Code128(tracking, barHeight=15*mm,barWidth=0.6* mm)
    bc.drawOn(c, m + (w - bc.width)/2, curr_y - 20*mm)

    _draw_text(c, label_w/2, curr_y - 25*mm, tracking, align='center')

    curr_y -= bc_h

    # GRID
    grid_h = 10 * mm
    col_w = w / 2

    c.roundRect(m, curr_y - grid_h, w, grid_h, 3, stroke=1, fill=0)

    _draw_text(c, m + 2*mm, curr_y - 4*mm, "DATE", size=7)
    _draw_text(c, m + 2*mm, curr_y - 8*mm, created_date, size=9)

    c.setStrokeColor(colors.black)
    c.line(m + col_w, curr_y, m + col_w, curr_y - grid_h)

    _draw_text(c, m + col_w + 2*mm, curr_y - 4*mm, "REFERENCE", size=7)
    _draw_multiline_text(c, m + col_w + 2*mm, curr_y - 7*mm, ref_number, col_w - 4*mm, size=8)

    curr_y -= grid_h

    # GOVERNORATE
    gov_h = 12 * mm
    c.roundRect(m, curr_y - gov_h, w, gov_h, 4, stroke=1, fill=0)

    _draw_text(c, m + 2*mm, curr_y - 4*mm, "GOVERNORATE", size=7)
    _draw_text(c, label_w / 2, curr_y - 9*mm, dest_city, align='center', size=13)

    curr_y -= gov_h

    # DETAILS
    details_h = 42 * mm
    c.roundRect(m, curr_y - details_h, w, details_h, 4, stroke=1, fill=0)

    _draw_text(c, m + 2*mm, curr_y - 5*mm, "SHIP FROM", size=7)
    _draw_text(c, m + 2*mm, curr_y - 10*mm, company.name, size=10)

    _draw_text(c, m + 2*mm, curr_y - 18*mm, "SHIP TO", size=7)

    _draw_text(c, m + 2*mm, curr_y - 24*mm, receiver.name, size=12)

    _draw_text(
        c,
        m + 2*mm,
        curr_y - 29*mm,
        f"{receiver.city} - {receiver.get_state_display()}",
        size=10
    )

    _draw_multiline_text(
        c,
        m + 2*mm,
        curr_y - 35*mm,
        receiver.street,
        w - 4*mm,
        size=9
    )

    curr_y -= details_h

    # CONTACT
    contact_h = 18 * mm
    c.roundRect(m, curr_y - contact_h, w, contact_h, 4, stroke=1, fill=0)

    _draw_text(c, m + 2*mm, curr_y - 5*mm, "CONTACT PHONE", size=7)
    _draw_text(c, label_w / 2, curr_y - 11*mm, primary_phone, align='center', size=14)

    if secondary_phone and secondary_phone != primary_phone:
        _draw_text(
            c,
            label_w / 2,
            curr_y - 15*mm,
            f"ALT: {secondary_phone}",
            align='center',
            size=10
        )

    curr_y -= contact_h

    # DESCRIPTION
    _draw_text(c, m + 2*mm, curr_y - 5*mm, "DESCRIPTION", size=7)

    _draw_multiline_text(
        c,
        m + 2*mm,
        curr_y - 10*mm,
        shipment.content_description,
        w - 4*mm,
        size=10
    )

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()