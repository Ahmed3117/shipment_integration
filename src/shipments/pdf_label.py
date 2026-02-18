"""
Modern & Information-Rich PDF Shipping Label Generator
Ensures all Aramex-style data is present and perfectly formatted on a single page.
"""

import io
from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

# Try to import arabic reshaping for proper RTL text
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC = True
except ImportError:
    HAS_ARABIC = False

# ─── Font Registration ───────────────────────────────────────────────────────

FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_BOLD_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
ARABIC_FONT_PATH = '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf'

_fonts_registered = False

def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont('DejaVu', FONT_PATH))
    pdfmetrics.registerFont(TTFont('DejaVuBold', FONT_BOLD_PATH))
    try:
        pdfmetrics.registerFont(TTFont('NotoArabic', ARABIC_FONT_PATH))
    except Exception:
        pass
    _fonts_registered = True


def _shape_arabic(text):
    if not text or not HAS_ARABIC:
        return text or ''
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)


def _has_arabic(text):
    if not text:
        return False
    return any('\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F'
               or '\uFB50' <= c <= '\uFDFF' or '\uFE70' <= c <= '\uFEFF'
               for c in str(text))


def _draw_text(c, x, y, text, font='DejaVu', size=9, bold=False, align='left', color=colors.black):
    text = str(text) if text else ''
    font_name = 'DejaVuBold' if bold else font
    c.setFillColor(color)
    
    if _has_arabic(text):
        shaped = _shape_arabic(text)
        try:
            c.setFont('NotoArabic', size)
        except Exception:
            c.setFont(font_name, size)
    else:
        c.setFont(font_name, size)
        shaped = text

    if align == 'center':
        c.drawCentredString(x, y, shaped)
    elif align == 'right':
        c.drawRightString(x, y, shaped)
    else:
        c.drawString(x, y, shaped)


def generate_shipment_label_pdf(shipment):
    _register_fonts()
    buffer = io.BytesIO()

    # A6 is standard for thermal shipping labels (105x148mm)
    label_w, label_h = 105 * mm, 148 * mm
    c = canvas.Canvas(buffer, pagesize=(label_w, label_h))
    c.setTitle(f'Label - {shipment.tracking_number}')

    # ── Data Fetching ─────────────────────────────────────────────────────
    
    company = shipment.company
    sender = shipment.sender_address
    receiver = shipment.receiver_address
    service = shipment.service_type
    tracking = shipment.tracking_number
    ref_number = shipment.reference_number or 'N/A'
    weight = shipment.weight or 0
    cod_value = shipment.estimated_cost or 0
    description = shipment.content_description or ''
    created_date = shipment.created_at.strftime('%Y-%m-%d') if shipment.created_at else ''
    
    dest_city = receiver.get_state_display() if receiver else 'N/A'
    origin_city = sender.get_state_display() if sender else 'N/A'
    service_code = service.code if service else 'DOM'

    # ── Layout Config ─────────────────────────────────────────────────────
    
    m = 4 * mm
    w = label_w - 2 * m
    curr_y = label_h - m

    # ── 1. HEADER (Logo Area + Destination) ───────────────────────────────
    
    header_h = 22 * mm
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    
    # Left: Company Brand
    c.setFillColor(colors.HexColor('#212121'))
    c.rect(m, curr_y - header_h, w * 0.7, header_h, fill=1, stroke=1)
    c.setFillColor(colors.white)
    _draw_text(c, m + 3 * mm, curr_y - 12 * mm, company.name.upper(), bold=True, size=16, color=colors.white)
    _draw_text(c, m + 3 * mm, curr_y - 18 * mm, f"ORIGIN: {origin_city[:3].upper()}", size=7, color=colors.white)
    
    # Right: Destination Code
    c.setFillColor(colors.white)
    c.rect(m + w * 0.7, curr_y - header_h, w * 0.3, header_h, fill=1, stroke=1)
    _draw_text(c, m + w * 0.85, curr_y - 8 * mm, "DEST", size=7, align='center', bold=True)
    _draw_text(c, m + w * 0.85, curr_y - 18 * mm, dest_city[:3].upper(), size=22, align='center', bold=True)
    
    curr_y -= header_h

    # ── 2. BARCODE SECTION ────────────────────────────────────────────────
    
    bc_area_h = 28 * mm
    c.rect(m, curr_y - bc_area_h, w, bc_area_h, stroke=1)
    
    # Barcode using ReportLab's internal generator (No Pillow dependency)
    try:
        bc = code128.Code128(tracking, barHeight=15*mm, barWidth=1.2)
        # Center the barcode
        bc_w = bc.width
        draw_x = m + (w - bc_w) / 2
        bc.drawOn(c, draw_x, curr_y - 20 * mm)
        _draw_text(c, m + w/2, curr_y - 25 * mm, tracking, bold=True, size=12, align='center')
    except Exception:
        _draw_text(c, m + w/2, curr_y - 15 * mm, "BARCODE ERROR", align='center')

    curr_y -= bc_area_h

    # ── 3. INFO GRID (Date, Ref, Service) ─────────────────────────────────
    
    grid_h = 10 * mm
    c.rect(m, curr_y - grid_h, w, grid_h, stroke=1)
    
    col_w = w / 3
    _draw_text(c, m + 2*mm, curr_y - 4*mm, "DATE", size=6, bold=True)
    _draw_text(c, m + 2*mm, curr_y - 8*mm, created_date, size=8)
    
    c.line(m + col_w, curr_y, m + col_w, curr_y - grid_h)
    _draw_text(c, m + col_w + 2*mm, curr_y - 4*mm, "REFERENCE", size=6, bold=True)
    _draw_text(c, m + col_w + 2*mm, curr_y - 8*mm, ref_number, size=7)
    
    c.line(m + 2*col_w, curr_y, m + 2*col_w, curr_y - grid_h)
    _draw_text(c, m + 2*col_w + 2*mm, curr_y - 4*mm, "SERVICE", size=6, bold=True)
    _draw_text(c, m + 2*col_w + 2*mm, curr_y - 8*mm, f"{service_code} / 1 PC", size=8)
    
    curr_y -= grid_h

    # ── 4. SHIPPER & CONSIGNEE DETAILS ────────────────────────────────────
    
    details_h = 42 * mm
    c.rect(m, curr_y - details_h, w, details_h, stroke=1)
    
    # Shipper (From)
    sy = curr_y - 4*mm
    _draw_text(c, m + 2*mm, sy, "SHIP FROM (SENDER)", size=6, bold=True, color=colors.grey)
    _draw_text(c, m + 2*mm, sy - 4*mm, company.name, bold=True, size=8)
    _draw_text(c, m + 2*mm, sy - 8*mm, sender.street if sender else company.address, size=7)
    _draw_text(c, m + 2*mm, sy - 12*mm, f"Tel: {sender.phone if sender else company.phone}", size=8)
    
    c.line(m + 2*mm, sy - 14*mm, m + w - 2*mm, sy - 14*mm)
    
    # Consignee (To)
    ty = sy - 18 * mm
    _draw_text(c, m + 2*mm, ty, "SHIP TO (RECEIVER)", size=6, bold=True, color=colors.grey)
    _draw_text(c, m + 2*mm, ty - 5*mm, (receiver.name if receiver else 'N/A'), bold=True, size=11)
    
    addr_parts = [receiver.street if receiver else '', receiver.city if receiver else '', dest_city]
    if receiver and receiver.zip_code:
        addr_parts.append(f"({receiver.zip_code})")
    addr = ", ".join(filter(None, addr_parts))
    
    # Address wrapping (Basic)
    if len(addr) > 50:
        _draw_text(c, m + 2*mm, ty - 10*mm, addr[:50], size=9)
        _draw_text(c, m + 2*mm, ty - 14*mm, addr[50:100], size=9)
    else:
        _draw_text(c, m + 2*mm, ty - 10*mm, addr, size=9)
        
    _draw_text(c, m + 2*mm, ty - 20 * mm, f"TEL: {receiver.phone if receiver else ''}", bold=True, size=10)
    
    curr_y -= details_h

    # ── 5. WEIGHT & COD (Highlights) ──────────────────────────────────────
    
    highlight_h = 16 * mm
    c.rect(m, curr_y - highlight_h, w, highlight_h, stroke=1)
    
    # Weight & Dimensions
    _draw_text(c, m + 2*mm, curr_y - 5*mm, "WEIGHT / DIMENSIONS", size=6, bold=True)
    dims = f"{shipment.length or 0}x{shipment.width or 0}x{shipment.height or 0} cm"
    _draw_text(c, m + 2*mm, curr_y - 11*mm, f"{weight} KG / {dims}", size=9, bold=True)
    
    # COD Box
    c.line(m + w * 0.45, curr_y, m + w * 0.45, curr_y - highlight_h)
    
    if cod_value > 0:
        c.setFillColor(colors.HexColor('#FFF9C4'))
        c.rect(m + w * 0.45, curr_y - highlight_h, w * 0.55, highlight_h, fill=1, stroke=0)
        c.setFillColor(colors.black)
        _draw_text(c, m + w * 0.5, curr_y - 5*mm, "CASH ON DELIVERY", size=6, bold=True)
        _draw_text(c, m + w - 3*mm, curr_y - 11*mm, f"{cod_value:,.2f} EGP", align='right', bold=True, size=14)
    else:
        c.setFillColor(colors.HexColor('#E8F5E9')) # Light green for prepaid
        c.rect(m + w * 0.45, curr_y - highlight_h, w * 0.55, highlight_h, fill=1, stroke=0)
        c.setFillColor(colors.black)
        _draw_text(c, m + w * 0.72, curr_y - 10*mm, "PREPAID", align='center', bold=True, size=14)
    
    curr_y -= highlight_h

    # ── 6. DESCRIPTION & REMARKS ──────────────────────────────────────────
    
    footer_h = label_h - (label_h - curr_y) - m
    c.rect(m, m, w, footer_h, stroke=1)
    
    _draw_text(c, m + 2*mm, footer_h + m - 4*mm, "DESCRIPTION / REMARKS:", size=6, bold=True)
    _draw_text(c, m + 2*mm, footer_h + m - 8*mm, description[:150], size=8)
    
    _draw_text(c, label_w/2, 2*mm, f"Powered by {company.name} Integration", size=5, align='center', color=colors.grey)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
