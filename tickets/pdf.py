import io
import os
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Türkçe karakter uyumu için sistem fontunu kaydet
FONT_NAME = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'

try:
    font_regular = "C:/Windows/Fonts/arial.ttf"
    font_bold = "C:/Windows/Fonts/arialbd.ttf"
    if os.path.exists(font_regular) and os.path.exists(font_bold):
        pdfmetrics.registerFont(TTFont('AppArial', font_regular))
        pdfmetrics.registerFont(TTFont('AppArialBold', font_bold))
        FONT_NAME = 'AppArial'
        FONT_BOLD = 'AppArialBold'
except Exception:
    pass


def generate_ticket_pdf(ticket):
    """
    Destek talebini, detaylarını, SLA metriklerini ve yorum geçmişini
    resmi ve kurumsal bir A4 PDF belgesi olarak üretir.
    BytesIO akışı döndürür.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        fontName=FONT_BOLD,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e293b")
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b")
    )
    heading_style = ParagraphStyle(
        'SectionHeading',
        fontName=FONT_BOLD,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'BodyTextCustom',
        fontName=FONT_NAME,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    meta_label_style = ParagraphStyle(
        'MetaLabel',
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569")
    )
    meta_val_style = ParagraphStyle(
        'MetaVal',
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f172a")
    )
    solution_style = ParagraphStyle(
        'SolutionText',
        fontName=FONT_NAME,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#065f46")
    )

    story = []

    # 1. BAŞLIK VE ANTET
    header_data = [
        [
            Paragraph(f"DESTEK TALEBİ RAPORU", title_style),
            Paragraph(f"<b>Rapor Tarihi:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}", subtitle_style)
        ],
        [
            Paragraph(f"<b>Talep No:</b> #{ticket.ticket_number} | <b>Durum:</b> {ticket.get_status_display()}", subtitle_style),
            Paragraph(f"<b>Sistem:</b> Destek Bilet Yönetimi", subtitle_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[340, 180])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceBefore=8, spaceAfter=14))

    # 2. TALEP METADATA TABLOSU
    cat_name = ticket.category.name if ticket.category else "Kategorisiz"
    creator = ticket.created_by.get_full_name() or ticket.created_by.username
    assignee = ticket.assigned_to.get_full_name() or ticket.assigned_to.username if ticket.assigned_to else "Atanmadı"
    created_str = ticket.created_at.strftime('%d.%m.%Y %H:%M') if ticket.created_at else "-"
    sla_status = "SLA Aşıldı!" if ticket.is_sla_breached else ("İlk Yanıt Verildi" if ticket.first_response_at else "Zamanında")

    meta_grid = [
        [
            Paragraph("Başlık:", meta_label_style), Paragraph(ticket.title, meta_val_style),
            Paragraph("Kategori:", meta_label_style), Paragraph(cat_name, meta_val_style),
        ],
        [
            Paragraph("Öncelik:", meta_label_style), Paragraph(ticket.get_priority_display(), meta_val_style),
            Paragraph("Durum:", meta_label_style), Paragraph(ticket.get_status_display(), meta_val_style),
        ],
        [
            Paragraph("Oluşturan:", meta_label_style), Paragraph(f"{creator} ({ticket.created_by.email or '-'})", meta_val_style),
            Paragraph("Atanan Personel:", meta_label_style), Paragraph(assignee, meta_val_style),
        ],
        [
            Paragraph("Oluşturulma:", meta_label_style), Paragraph(created_str, meta_val_style),
            Paragraph("SLA Durumu:", meta_label_style), Paragraph(sla_status, meta_val_style),
        ],
    ]
    meta_table = Table(meta_grid, colWidths=[80, 180, 80, 180])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # 3. TALEP AÇIKLAMASI
    story.append(Paragraph("Talep Detayı ve Müşteri Açıklaması", heading_style))
    desc_clean = ticket.description.replace('\n', '<br/>')
    desc_p = Paragraph(desc_clean, body_style)
    desc_table = Table([[desc_p]], colWidths=[520])
    desc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(desc_table)
    story.append(Spacer(1, 14))

    # 4. EN İYİ YANIT / ONAYLI ÇÖZÜM
    solution_comment = ticket.comments.filter(is_solution=True).first()
    if solution_comment:
        story.append(Paragraph("✅ Onaylanmış Çözüm (En İyi Yanıt)", heading_style))
        sol_author = solution_comment.author.get_full_name() or solution_comment.author.username
        sol_date = solution_comment.created_at.strftime('%d.%m.%Y %H:%M')
        sol_content = solution_comment.content.replace('\n', '<br/>')
        sol_text = f"<b>{sol_author}</b> ({sol_date}):<br/>{sol_content}"
        sol_table = Table([[Paragraph(sol_text, solution_style)]], colWidths=[520])
        sol_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#ecfdf5")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#10b981")),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(sol_table)
        story.append(Spacer(1, 14))

    # 5. YANIT VE YORUM GEÇMİŞİ
    comments = list(ticket.comments.filter(is_internal=False).order_by('created_at'))
    if comments:
        story.append(Paragraph(f"İletişim Geçmişi ve Yanıtlar ({len(comments)} Yanıt)", heading_style))
        for c in comments:
            author_name = c.author.get_full_name() or c.author.username
            role_badge = " [Yetkili]" if c.author.is_staff else " [Kullanıcı]"
            c_date = c.created_at.strftime('%d.%m.%Y %H:%M')
            c_body = c.content.replace('\n', '<br/>')
            sol_badge = " <b>[ONAYLI ÇÖZÜM]</b>" if c.is_solution else ""
            
            c_header = f"<b>{author_name}{role_badge}</b> - <font color='#64748b'>{c_date}</font>{sol_badge}"
            c_table = Table([
                [Paragraph(c_header, meta_label_style)],
                [Paragraph(c_body, body_style)]
            ], colWidths=[520])
            c_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#ffffff")),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.HexColor("#f1f5f9")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(KeepTogether([c_table, Spacer(1, 6)]))

    # 6. ALT BİLGİ (FOOTER)
    def add_footer(canvas, document):
        canvas.saveState()
        canvas.setFont(FONT_NAME, 8)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        page_num = canvas.getPageNumber()
        footer_text = f"Support Ticket System | #{ticket.ticket_number} Resmi Arşiv Raporu | Sayfa {page_num}"
        canvas.drawRightString(A4[0] - 36, 20, footer_text)
        canvas.drawString(36, 20, "Gizli & Kurumsal Kullanım")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    return buffer
