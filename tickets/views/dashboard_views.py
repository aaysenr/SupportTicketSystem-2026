import csv
import json
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden, FileResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone

from ..models import Ticket, TicketRating
from ..pdf import generate_ticket_pdf


def _safe_get_ticket_creator_username(ticket, default="Silinmiş Kullanıcı"):
    """Bilet sahibinin adını RelatedObjectDoesNotExist istisnasına karşı güvenli bir şekilde döndürür."""
    try:
        return ticket.created_by.username if ticket.created_by else default
    except (User.DoesNotExist, AttributeError, Exception):
        return default


def _safe_get_ticket_assignee_username(ticket, default="Atanmadı"):
    """Atanan yetkilinin adını güvenli bir şekilde döndürür."""
    try:
        return ticket.assigned_to.username if ticket.assigned_to else default
    except (User.DoesNotExist, AttributeError, Exception):
        return default



@login_required
def admin_dashboard_view(request):
    """
    Yöneticiler için İstatistik ve Analiz Dashboard'u.
    """
    # Güvenlik Kontrolü: Yalnızca yöneticiler girebilir!
    if not request.user.is_staff:
        messages.error(request, "Bu sayfayı görüntüleme yetkiniz yok!")
        return redirect('ticket_list')

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # RBAC Kapsam Belirleme:
    # Süper yönetici: Tüm sistemi kapsayan genel analiz (Tüm talepler)
    # Diğer adminler: Yalnızca kendi kategorileri ve kendilerine atanan talepler
    if is_superadmin:
        base_qs = Ticket.objects.all()
    elif profile and profile.assigned_categories.exists():
        allowed_cats = profile.assigned_categories.all()
        base_qs = Ticket.objects.filter(
            Q(category__in=allowed_cats) | Q(assigned_to=request.user)
        ).distinct()
    else:
        # Kategori tanımlanmamışsa sadece kendisine atanan talepleri analiz et
        base_qs = Ticket.objects.filter(assigned_to=request.user)

    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. Tekil SQL Koşullu Toplama (Conditional Aggregation) ile Tüm Metrikler (N+1 Sorgu Engellendi)
    metrics = base_qs.aggregate(
        total_tickets=Count('id'),
        open_tickets=Count('id', filter=Q(status='open')),
        in_progress_tickets=Count('id', filter=Q(status='in_progress')),
        resolved_tickets=Count('id', filter=Q(status='resolved')),
        priority_low=Count('id', filter=Q(priority='low')),
        priority_medium=Count('id', filter=Q(priority='medium')),
        priority_high=Count('id', filter=Q(priority='high')),
        priority_urgent=Count('id', filter=Q(priority='urgent')),
        resolved_this_month=Count('id', filter=Q(status='resolved', updated_at__gte=first_day_of_month)),
        created_this_month=Count('id', filter=Q(created_at__gte=first_day_of_month)),
        sla_breached_count=Count('id', filter=Q(status__in=['open', 'in_progress'], sla_deadline__isnull=False, sla_deadline__lt=now)),
    )

    total_tickets = metrics['total_tickets']
    open_tickets = metrics['open_tickets']
    in_progress_tickets = metrics['in_progress_tickets']
    resolved_tickets = metrics['resolved_tickets']
    urgent_tickets = metrics['priority_urgent']
    resolved_this_month = metrics['resolved_this_month']
    created_this_month = metrics['created_this_month']
    sla_breached_count = metrics['sla_breached_count']

    # 2. SLA Geciken İlk 5 Talep (Bellek tüketimi engellendi; SQL index ve LIMIT 5 ile hızlı çekim)
    sla_breached_tickets = list(
        base_qs.filter(
            status__in=['open', 'in_progress'],
            sla_deadline__isnull=False,
            sla_deadline__lt=now
        ).select_related('created_by', 'category').order_by('sla_deadline')[:5]
    )

    # 3. Müşteri Memnuniyet (CSAT) Metrikleri (Tekil SQL aggregate ile)
    csat_stats = TicketRating.objects.filter(ticket__in=base_qs).aggregate(
        count=Count('id'),
        avg=Avg('score'),
        satisfied=Count('id', filter=Q(score__gte=4))
    )
    csat_count = csat_stats['count']
    csat_avg = round(csat_stats['avg'], 1) if csat_stats['avg'] else 0.0
    satisfied_count = csat_stats['satisfied']
    satisfaction_rate = round((satisfied_count / csat_count) * 100, 1) if csat_count > 0 else 0

    # 3.b MTTR (Mean Time to Resolve / Ortalama Çözüm Süresi) Hesabı
    resolved_tickets_qs = base_qs.filter(status='resolved')
    mttr_stat = resolved_tickets_qs.annotate(
        resolution_time=ExpressionWrapper(F('updated_at') - F('created_at'), output_field=DurationField())
    ).aggregate(avg_res=Avg('resolution_time'))

    avg_res = mttr_stat['avg_res']
    if avg_res:
        total_seconds = max(0, int(avg_res.total_seconds()))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours >= 24:
            days = hours // 24
            rem_hours = hours % 24
            mttr_display = f"{days}g {rem_hours}s"
        elif hours > 0:
            mttr_display = f"{hours}s {minutes}dk"
        else:
            mttr_display = f"{minutes} dk"
        mttr_hours = round(total_seconds / 3600, 1)
    else:
        mttr_display = "-"
        mttr_hours = 0

    # 4. Kategori Dağılımı Verileri (Chart.js İçin)
    # Kapsamdaki taleplerin kategorilerine göre dağılımı (Süper admin tüm sistem, diğer adminler kendi talepleri)
    cat_distribution = list(
        base_qs.filter(category__isnull=False)
        .values('category__name')
        .annotate(ticket_count=Count('id'))
        .order_by('-ticket_count')
    )
    category_labels = [c['category__name'] for c in cat_distribution]
    category_counts = [c['ticket_count'] for c in cat_distribution]
    uncat_count = base_qs.filter(category__isnull=True).count()
    if uncat_count > 0:
        category_labels.append("Kategorisiz")
        category_counts.append(uncat_count)

    # 5. Öncelik Dağılımı Verileri
    priority_data = {
        'Düşük': metrics['priority_low'],
        'Orta': metrics['priority_medium'],
        'Yüksek': metrics['priority_high'],
        'Acil': metrics['priority_urgent'],
    }

    # 6. Aylık CSAT Memnuniyet Trendi (Son 6 Ay)
    csat_trend_labels = []
    csat_trend_values = []
    month_names_tr = {
        1: 'Oca', 2: 'Şub', 3: 'Mar', 4: 'Nis', 5: 'May', 6: 'Haz',
        7: 'Tem', 8: 'Ağu', 9: 'Eyl', 10: 'Eki', 11: 'Kas', 12: 'Ara'
    }
    today = timezone.now().date()
    for i in range(5, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        m_start = timezone.make_aware(datetime(year, month, 1, 0, 0, 0))
        if month == 12:
            m_end = timezone.make_aware(datetime(year + 1, 1, 1, 0, 0, 0))
        else:
            m_end = timezone.make_aware(datetime(year, month + 1, 1, 0, 0, 0))

        m_stat = TicketRating.objects.filter(
            ticket__in=base_qs,
            created_at__gte=m_start,
            created_at__lt=m_end
        ).aggregate(avg=Avg('score'))

        val = round(m_stat['avg'], 2) if m_stat['avg'] is not None else 0.0
        csat_trend_labels.append(f"{month_names_tr.get(month, '')} {year}")
        csat_trend_values.append(val)

    # 7. Son Müşteri Değerlendirmeleri ve Geri Bildirimleri (CSAT - Yalnızca Süper Adminler)
    csat_assigned = request.GET.get('csat_assigned', '').strip()
    csat_ticket_id = request.GET.get('csat_ticket_id', '').strip()
    csat_user_id = request.GET.get('csat_user_id', '').strip()
    csat_sort = request.GET.get('csat_sort', 'newest').strip()

    if is_superadmin:
        csat_qs = TicketRating.objects.filter(ticket__in=base_qs).select_related('ticket', 'user', 'ticket__assigned_to')

        if csat_assigned:
            if csat_assigned == 'unassigned':
                csat_qs = csat_qs.filter(ticket__assigned_to__isnull=True)
            elif csat_assigned.isdigit():
                csat_qs = csat_qs.filter(ticket__assigned_to_id=int(csat_assigned))

        if csat_ticket_id:
            # Temiz id ya da DES-00010 gibi format desteği
            clean_t_id = csat_ticket_id.upper().replace('DES-', '').replace('#', '').strip()
            if clean_t_id.isdigit():
                csat_qs = csat_qs.filter(ticket_id=int(clean_t_id))
            else:
                csat_qs = csat_qs.filter(ticket__title__icontains=csat_ticket_id)

        if csat_user_id:
            if csat_user_id.isdigit():
                csat_qs = csat_qs.filter(Q(user_id=int(csat_user_id)) | Q(user__username__icontains=csat_user_id))
            else:
                csat_qs = csat_qs.filter(Q(user__username__icontains=csat_user_id) | Q(user__email__icontains=csat_user_id) | Q(user__first_name__icontains=csat_user_id) | Q(user__last_name__icontains=csat_user_id))

        if csat_sort == 'oldest':
            csat_qs = csat_qs.order_by('created_at')
        else:
            csat_qs = csat_qs.order_by('-created_at')

        csat_ratings = csat_qs[:50]
    else:
        csat_ratings = []

    staff_users = User.objects.filter(is_staff=True).order_by('first_name', 'username')

    context = {
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'urgent_tickets': urgent_tickets,
        'resolved_this_month': resolved_this_month,
        'created_this_month': created_this_month,
        'user_profile': profile,
        'is_superadmin': is_superadmin,
        
        # SLA & CSAT Metrikleri
        'sla_breached_count': sla_breached_count,
        'sla_breached_tickets': sla_breached_tickets[:5],
        'csat_count': csat_count,
        'csat_avg': csat_avg,
        'satisfaction_rate': satisfaction_rate,
        'mttr_display': mttr_display,
        'mttr_hours': mttr_hours,
        'csat_ratings': csat_ratings,
        'staff_users': staff_users,
        'csat_assigned': csat_assigned,
        'csat_ticket_id': csat_ticket_id,
        'csat_user_id': csat_user_id,
        'csat_sort': csat_sort,
        
        # Chart.js'in JSON formatında okuyabilmesi için:
        'category_labels_json': json.dumps(category_labels),
        'category_counts_json': json.dumps(category_counts),
        'priority_labels_json': json.dumps(list(priority_data.keys())),
        'priority_counts_json': json.dumps(list(priority_data.values())),
        'csat_trend_labels_json': json.dumps(csat_trend_labels),
        'csat_trend_values_json': json.dumps(csat_trend_values),
    }

    return render(request, 'tickets/dashboard.html', context)





def _get_filtered_tickets_qs(request):
    """Excel ve CSV export için ortak filtrelenmiş talep sorgusunu üretir."""
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    if is_superadmin:
        base_qs = Ticket.objects.all()
    elif profile and profile.assigned_categories.exists():
        allowed_cats = profile.assigned_categories.all()
        base_qs = Ticket.objects.filter(
            Q(category__in=allowed_cats) | Q(assigned_to=request.user)
        ).distinct()
    else:
        base_qs = Ticket.objects.filter(assigned_to=request.user)

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    priority = request.GET.get('priority', '').strip()
    category_id = request.GET.get('category', '').strip()
    assigned_to = request.GET.get('assigned_to', '').strip()
    tag = request.GET.get('tag', '').strip()
    solution = request.GET.get('solution', 'all').strip()
    mine = request.GET.get('mine') == '1'

    tickets = base_qs
    if q:
        tickets = tickets.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if status:
        tickets = tickets.filter(status=status)
    if priority:
        tickets = tickets.filter(priority=priority)
    if category_id:
        tickets = tickets.filter(category_id=category_id)
    if assigned_to:
        if assigned_to == 'unassigned':
            tickets = tickets.filter(assigned_to__isnull=True)
        else:
            tickets = tickets.filter(assigned_to_id=assigned_to)
    if tag:
        tickets = tickets.filter(Q(tags__slug=tag) | Q(tags__name=tag)).distinct()
    if solution == 'solved':
        tickets = tickets.filter(Q(status='resolved') | Q(comments__is_solution=True)).distinct()
    elif solution == 'unsolved':
        tickets = tickets.exclude(status='resolved').exclude(comments__is_solution=True).distinct()
    if mine:
        tickets = tickets.filter(created_by=request.user)

    return tickets.select_related('created_by', 'category', 'assigned_to').prefetch_related('comments', 'tags').annotate(comment_count=Count('comments', distinct=True)).order_by('-created_at')




@login_required
def export_tickets_csv(request):
    """
    Destek taleplerini Excel uyumlu CSV (UTF-8 BOM ve ';' ayracı) formatında dışa aktarır.
    Aktif filtreleri ve RBAC departman yetkilendirmesini uygular.
    """
    if not request.user.is_staff:
        messages.error(request, "Rapor dışa aktarma yetkiniz bulunmamaktadır!")
        return redirect('ticket_list')

    tickets = _get_filtered_tickets_qs(request)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"destek_talepleri_raporu_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Talep No', 'Başlık', 'Kategori', 'Etiketler', 'Öncelik', 'Durum',
        'Oluşturan', 'Atanan Yönetici', 'Gizlilik', 'Oluşturulma Tarihi',
        'Son Güncelleme', 'İlk Yanıt Tarihi', 'SLA Durumu', 'Yorum Sayısı'
    ])

    for t in tickets:
        sla_text = "SLA Aşıldı" if t.is_sla_breached else ("İlk Yanıt Verildi" if t.first_response_at else "Zamanında Devam Ediyor")
        tags_str = ", ".join([f"#{tg.name}" for tg in t.tags.all()]) if hasattr(t, 'tags') else ""
        writer.writerow([
            t.ticket_number,
            t.title,
            t.category.name if t.category else "Kategorisiz",
            tags_str,
            t.get_priority_display(),
            t.get_status_display(),
            _safe_get_ticket_creator_username(t),
            _safe_get_ticket_assignee_username(t),
            "Herkese Açık" if t.is_public else "Özel / Gizli",
            t.created_at.strftime('%d.%m.%Y %H:%M') if t.created_at else "",
            t.updated_at.strftime('%d.%m.%Y %H:%M') if t.updated_at else "",
            t.first_response_at.strftime('%d.%m.%Y %H:%M') if t.first_response_at else "Henüz Yanıtlanmadı",
            sla_text,
            getattr(t, 'comment_count', t.comments.count())
        ])

    return response




@login_required
def export_tickets_excel(request):
    """
    Destek taleplerini biçimlendirilmiş Microsoft Excel (.xlsx) formatında dışa aktarır.
    openpyxl kütüphanesini kullanarak kurumsal renkler, otomatik sütun genişlikleri
    ve başlık filtreleme desteği sunar.
    """
    if not request.user.is_staff:
        messages.error(request, "Rapor dışa aktarma yetkiniz bulunmamaktadır!")
        return redirect('ticket_list')

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Destek Talepleri"

    headers = [
        'Talep No', 'Başlık', 'Kategori', 'Etiketler', 'Öncelik', 'Durum',
        'Oluşturan', 'Atanan Yönetici', 'Gizlilik', 'Oluşturulma Tarihi',
        'Son Güncelleme', 'İlk Yanıt Tarihi', 'SLA Durumu', 'Yorum Sayısı'
    ]
    ws.append(headers)

    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1D4ED8', end_color='1D4ED8', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    tickets = _get_filtered_tickets_qs(request)

    for t in tickets:
        sla_text = "SLA Aşıldı" if t.is_sla_breached else ("İlk Yanıt Verildi" if t.first_response_at else "Zamanında Devam Ediyor")
        tags_str = ", ".join([f"#{tg.name}" for tg in t.tags.all()]) if hasattr(t, 'tags') else ""
        row = [
            t.ticket_number,
            t.title,
            t.category.name if t.category else "Kategorisiz",
            tags_str,
            t.get_priority_display(),
            t.get_status_display(),
            _safe_get_ticket_creator_username(t),
            _safe_get_ticket_assignee_username(t),
            "Herkese Açık" if t.is_public else "Özel / Gizli",
            t.created_at.strftime('%d.%m.%Y %H:%M') if t.created_at else "",
            t.updated_at.strftime('%d.%m.%Y %H:%M') if t.updated_at else "",
            t.first_response_at.strftime('%d.%m.%Y %H:%M') if t.first_response_at else "Henüz Yanıtlanmadı",
            sla_text,
            getattr(t, 'comment_count', t.comments.count())
        ]
        ws.append(row)

    # Otomatik sütun genişliği hesaplama
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"destek_talepleri_raporu_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response



@login_required
def export_ticket_pdf(request, pk):
    """
    Belirli bir destek talebini antetli, kurumsal ve Türkçe uyumlu A4 PDF belgesi olarak sunar.
    Gizli taleplerde yetki kontrolü (RBAC) uygular.
    """
    ticket = get_object_or_404(Ticket.objects.select_related('created_by', 'category', 'assigned_to'), pk=pk)

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # Gizlilik & RBAC Kontrolü:
    if not ticket.is_public and ticket.created_by != request.user and ticket.assigned_to != request.user and not is_superadmin:
        if not request.user.is_staff:
            return HttpResponseForbidden("Bu özel talebin PDF raporunu indirme yetkiniz bulunmamaktadır.")
        elif profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                return HttpResponseForbidden("Bu kategoriye ait talebin PDF raporunu indirme yetkiniz bulunmamaktadır.")

    pdf_buffer = generate_ticket_pdf(ticket)
    filename = f"talep_{ticket.ticket_number}_{timezone.now().strftime('%Y%m%d')}.pdf"
    return FileResponse(pdf_buffer, as_attachment=True, filename=filename, content_type='application/pdf')


