import os
import mimetypes
import json
import re
import threading
import logging
import csv
import openpyxl
from datetime import datetime, date

import nh3
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, FileResponse, HttpResponseForbidden, Http404, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Avg, F
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.core.cache import cache
from django.utils import timezone
from django.utils.text import slugify

from ..models import (
    Ticket, TicketComment, Category, EmailVerification, TicketActivityLog,
    Notification, ChatGroup, ChatMessage, UserChatPreference, UserProfile, KnowledgeBaseArticle,
    TicketRating, CannedResponse, TicketTag
)
from ..forms import TicketForm, CommentForm, UserRegisterForm, UserProfileForm
from ..totp import (
    generate_totp_secret, get_totp_token, verify_totp_token,
    get_totp_uri, generate_qr_code_data_uri
)
from ..pdf import generate_ticket_pdf
from ..webhooks import send_outgoing_webhook
from ..copilot import suggest_category_and_priority, generate_ticket_summary
from ..consumers import ALLOWED_TAGS, ALLOWED_ATTRIBUTES
from .common import send_notification_email, _async_email_worker

logger = logging.getLogger(__name__)


@login_required
def ticket_list(request):
    """
    Talepleri listeleyen görünüm.
    - Yöneticiler (is_staff) TÜM talepleri görür.
    - Normal kullanıcılar SADECE kendi açtıkları talepleri görür.
    """
    filter_mine = request.GET.get('mine') == '1' or request.GET.get('filter') == 'mine'
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # 1. Kullanıcının rolüne ve seçili filtreye göre temel talep kümesini belirliyoruz (RBAC)
    if request.user.is_staff or is_superadmin:
        if filter_mine:
            base_tickets = Ticket.objects.filter(created_by=request.user).select_related('created_by', 'category', 'assigned_to')
        elif is_superadmin:
            # Süper Yönetici: Sistemdeki tüm talepleri eksiksiz görür
            base_tickets = Ticket.objects.all().select_related('created_by', 'category', 'assigned_to')
        elif profile and profile.assigned_categories.exists():
            # Teknik Destek / Finans Yetkilisi: Sorumlu olduğu kategoriler + kendisine atananlar + kendi açtığı talepler
            allowed_cats = profile.assigned_categories.all()
            base_tickets = Ticket.objects.filter(
                Q(category__in=allowed_cats) | Q(assigned_to=request.user) | Q(created_by=request.user)
            ).distinct().select_related('created_by', 'category', 'assigned_to')
        else:
            base_tickets = Ticket.objects.all().select_related('created_by', 'category', 'assigned_to')
    else:
        if filter_mine:
            # "Taleplerim" Sekmesi: Sadece kendi açtığı talepler (Özel + Genel)
            base_tickets = Ticket.objects.filter(created_by=request.user).select_related('created_by', 'category', 'assigned_to')
        else:
            # "Destek Sistemi" (Genel Forum Akışı): Herkese açık tüm talepler + kullanıcının kendi talepleri
            base_tickets = Ticket.objects.filter(
                Q(is_public=True) | Q(created_by=request.user)
            ).select_related('created_by', 'category', 'assigned_to')

    # 2. İstatistik Sayaçları (Koşullu Toplama - Tek SQL Sorgusu)
    counts = base_tickets.aggregate(
        total=Count('id'),
        open=Count('id', filter=Q(status='open')),
        in_progress=Count('id', filter=Q(status='in_progress')),
        resolved=Count('id', filter=Q(status='resolved')),
        urgent=Count('id', filter=Q(priority='urgent')),
    )
    total_count = counts['total']
    open_count = counts['open']
    in_progress_count = counts['in_progress']
    resolved_count = counts['resolved']
    urgent_count = counts['urgent']

    # 3. URL Arama ve Filtreleme İşlemleri
    tickets = base_tickets.annotate(comment_count=Count('comments')).select_related('created_by', 'category', 'assigned_to').prefetch_related('comments', 'tags')
    
    search_query = request.GET.get('q', '').strip()
    selected_status = request.GET.get('status', '').strip()
    selected_priority = request.GET.get('priority', '').strip()
    selected_category = request.GET.get('category', '').strip()
    selected_assigned = request.GET.get('assigned_to', '').strip()
    selected_tag = request.GET.get('tag', '').strip()
    selected_sort = request.GET.get('sort', 'newest').strip()
    selected_solution = request.GET.get('solution', 'all').strip()

    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    if selected_status:
        tickets = tickets.filter(status=selected_status)

    if selected_priority:
        tickets = tickets.filter(priority=selected_priority)

    if selected_category:
        tickets = tickets.filter(category_id=selected_category)

    if selected_assigned:
        if selected_assigned == 'unassigned':
            tickets = tickets.filter(assigned_to__isnull=True)
        else:
            tickets = tickets.filter(assigned_to_id=selected_assigned)

    if selected_tag:
        tickets = tickets.filter(Q(tags__slug=selected_tag) | Q(tags__name=selected_tag)).distinct()

    if selected_solution == 'solved':
        tickets = tickets.filter(Q(status='resolved') | Q(comments__is_solution=True)).distinct()
    elif selected_solution == 'unsolved':
        tickets = tickets.exclude(status='resolved').exclude(comments__is_solution=True).distinct()

    if selected_sort == 'oldest':
        tickets = tickets.order_by('created_at')
    elif selected_sort == 'most_commented':
        tickets = tickets.order_by('-comment_count', '-created_at')
    else:
        tickets = tickets.order_by('-created_at')

    paginator = Paginator(tickets, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'tickets': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_status': selected_status,
        'selected_priority': selected_priority,
        'selected_category': selected_category,
        'selected_assigned': selected_assigned,
        'selected_tag': selected_tag,
        'selected_sort': selected_sort,
        'selected_solution': selected_solution,
        'filter_mine': filter_mine,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'total_count': total_count,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'urgent_count': urgent_count,
        'user_profile': profile,
        'is_superadmin': is_superadmin,
        'categories': Category.objects.all(),
        'all_tags': TicketTag.objects.all(),
        'tags': TicketTag.objects.all(),
        'staff_users': User.objects.filter(is_staff=True).order_by('username'),
    }

    return render(request, 'tickets/ticket_list.html', context)




@login_required
def ticket_detail(request, pk):
    """
    Tek bir destek talebinin detayını ve yorumlarını gösteren görünüm.
    """
    ticket = get_object_or_404(Ticket.objects.select_related('created_by', 'category', 'assigned_to'), pk=pk)

    # GİZLİLİK VE RBAC KONTROLÜ:
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    if not ticket.is_public and ticket.created_by != request.user and ticket.assigned_to != request.user and not is_superadmin:
        if not request.user.is_staff:
            messages.error(request, "Bu özel destek talebini görüntüleme yetkiniz yok!")
            return redirect('ticket_list')
        elif profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                messages.error(request, "Bu departman/kategoriye ait talepleri görüntüleme yetkiniz bulunmamaktadır!")
                return redirect('ticket_list')

    comments = ticket.comments.all()
    if not request.user.is_staff:
        comments = comments.filter(is_internal=False)
    comments = comments.select_related('author')

    if request.method == 'POST':
        comment_form = CommentForm(request.POST, request.FILES, user=request.user)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.save()

            # SLA Takibi: Destek yetkilisi yanıt verdiğinde ilk yanıt tarihini kaydet
            author_profile = getattr(comment.author, 'profile', None)
            is_staff_commenter = comment.author.is_staff or (author_profile and author_profile.is_staff_agent)
            if is_staff_commenter and not ticket.first_response_at:
                ticket.first_response_at = timezone.now()
                ticket.save(update_fields=['first_response_at'])


            
            # CANLI BİLDİRİM & E-POSTA 1: Talep sahibine bildirim (Yorumu yazan kişi talep sahibi değilse)
            if comment.author != ticket.created_by:
                Notification.objects.create(
                    recipient=ticket.created_by,
                    actor=comment.author,
                    ticket=ticket,
                    message=f"#{ticket.ticket_number} talebinize {comment.author.username} tarafından yanıt eklendi."
                )
                if ticket.created_by.email:
                    send_notification_email(
                        subject=f"[Destek Talebi] #{ticket.ticket_number} Talebinize Yeni Yanıt Geldi",
                        message=f"Merhaba {ticket.created_by.username},\n\n#{ticket.ticket_number} numaralı '{ticket.title}' başlıklı destek talebinize {comment.author.username} tarafından yeni bir yanıt eklendi:\n\n\"{comment.content}\"\n\nTalebi ve detayları görüntülemek için sisteme giriş yapabilirsiniz.\n\nİyi çalışmalar dileriz.",
                        recipient_list=[ticket.created_by.email]
                    )

            # CANLI BİLDİRİM & E-POSTA 2: Atanmış personele bildirim (Müşteri veya başka biri yanıt verdiğinde)
            if ticket.assigned_to and comment.author != ticket.assigned_to:
                Notification.objects.create(
                    recipient=ticket.assigned_to,
                    actor=comment.author,
                    ticket=ticket,
                    message=f"Sorumlu olduğunuz #{ticket.ticket_number} talebine {comment.author.username} tarafından yanıt eklendi."
                )
                if ticket.assigned_to.email:
                    send_notification_email(
                        subject=f"[Destek Talebi] Sorumlu Olduğunuz #{ticket.ticket_number} Talebine Yeni Yanıt Geldi",
                        message=f"Merhaba {ticket.assigned_to.username},\n\nSorumlusu olduğunuz #{ticket.ticket_number} numaralı '{ticket.title}' talebine {comment.author.username} tarafından yeni bir yanıt yazıldı:\n\n\"{comment.content}\"\n\nDetayları görüntülemek için sisteme giriş yapabilirsiniz.",
                        recipient_list=[ticket.assigned_to.email]
                    )

            # WebSocket Canlı Yorum Dağıtımı (Real-Time Broadcast)
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        f"ticket_{ticket.id}",
                        {
                            "type": "ticket_comment_broadcast",
                            "comment_id": comment.id,
                            "author_id": comment.author.id,
                            "author_name": comment.author.get_full_name() or comment.author.username,
                            "is_staff": comment.author.is_staff,
                            "is_internal": comment.is_internal,
                            "content": comment.content,
                            "attachment_url": comment.attachment.url if comment.attachment else "",
                            "attachment_name": os.path.basename(comment.attachment.name) if comment.attachment else "",
                            "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M")
                        }
                    )
            except Exception:
                pass

            messages.success(request, "Yorumunuz başarıyla eklendi.")
            return redirect('ticket_detail', pk=ticket.pk)

    else:
        comment_form = CommentForm(user=request.user)

    canned_responses = []
    if request.user.is_staff:
        canned_responses = CannedResponse.objects.filter(
            Q(category=ticket.category) | Q(category__isnull=True)
        )

    context = {
        'ticket': ticket,
        'comments': comments,
        'comment_form': comment_form,
        'activity_logs': ticket.activity_logs.all(),
        'has_solution': comments.filter(is_solution=True).exists(),
        'canned_responses': canned_responses,
    }

    return render(request, 'tickets/ticket_detail.html', context)




@login_required
def ticket_create(request): 
    """
    Yeni destek talebi oluşturma görünümü.
    GET isteği geldiğinde boş form gösterir, POST isteğinde doğrular ve kaydeder.
    """
    if request.method == 'POST':
        form = TicketForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            ticket.save()
            form.save_m2m()
            
            TicketActivityLog.objects.create(
               ticket=ticket,
               actor=request.user,
               action="Destek talebi oluşturuldu."
            )

            # CANLI BİLDİRİM & E-POSTA: Başka bir personele atanarak oluşturulduysa o personele bildir
            if ticket.assigned_to and ticket.assigned_to != request.user:
                Notification.objects.create(
                    recipient=ticket.assigned_to,
                    actor=request.user,
                    ticket=ticket,
                    message=f"#{ticket.ticket_number} talebi size atandı."
                )
                if ticket.assigned_to.email:
                    send_notification_email(
                        subject=f"[Destek Talebi] #{ticket.ticket_number} Talebi Size Atandı",
                        message=f"Merhaba {ticket.assigned_to.username},\n\n#{ticket.ticket_number} numaralı '{ticket.title}' başlıklı yeni destek talebi tarafınıza atanmıştır.\n\nDetayları incelemek için sisteme giriş yapabilirsiniz.",
                        recipient_list=[ticket.assigned_to.email]
                    )

            if ticket.created_by.email:
                send_notification_email(
                    subject=f"[Destek Talebi] #{ticket.ticket_number} Talebiniz Başarıyla Alındı",
                    message=f"Merhaba {ticket.created_by.username},\n\n#{ticket.ticket_number} numaralı '{ticket.title}' başlıklı destek talebiniz sisteme kaydolmuştur.\n\nDestek ekibimiz en kısa sürede talebinizi inceleyip yanıtlayacaktır.\n\nİyi günler dileriz.",
                    recipient_list=[ticket.created_by.email]
                )

            # Acil Durum Harici Webhook Tetikleyicisi (Slack / Discord / Teams)
            if ticket.priority == 'urgent':
                send_outgoing_webhook(ticket, event_type="urgent_ticket_created")

            messages.success(request, "Destek talebiniz başarıyla oluşturuldu.") 
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        form = TicketForm(user=request.user)

    return render(request, 'tickets/ticket_form.html', {'form': form})






@login_required
def ticket_edit(request, pk): 
    """
    Var olan bir destek talebini düzenleme ve durumunu güncelleme görünümü.
    """
    ticket = get_object_or_404(Ticket, pk=pk)
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # Güvenlik Kontrolü 1: Yetkisiz kullanıcı engeli
    if not request.user.is_staff and ticket.created_by != request.user:
        messages.error(request, "Bu destek talebini düzenleme yetkiniz yok!")
        return redirect('ticket_list')

    # RBAC Kontrolü: Personel başka birimin/kategorinin talebini düzenleyemez
    if request.user.is_staff and not is_superadmin and ticket.assigned_to != request.user and ticket.created_by != request.user:
        if profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                messages.error(request, "Bu departman/kategoriye ait talepleri düzenleme yetkiniz bulunmamaktadır!")
                return redirect('ticket_list')

    # Güvenlik Kontrolü 2: Normal kullanıcı çözülmüş/kapatılmış talebi düzenleyemesin
    if not request.user.is_staff and ticket.status in ['resolved', 'closed']:
        messages.error(request, "Çözülmüş veya kapatılmış destek talepleri düzenlenemez!")
        return redirect('ticket_detail', pk=ticket.pk)

    if request.method == 'POST':
        old_status = ticket.get_status_display()
        old_assigned = ticket.assigned_to.username if ticket.assigned_to else "Atanmadı"
        old_assigned_user = ticket.assigned_to
        
        form = TicketForm(request.POST, request.FILES, instance=ticket, user=request.user)

        if form.is_valid():
            updated_ticket = form.save()
            changes = []
            new_status = updated_ticket.get_status_display()
            new_assigned = updated_ticket.assigned_to.username if updated_ticket.assigned_to else "Atanmadı"

            # CANLI BİLDİRİM: Durum değiştiyse bildirim oluştur
            if old_status != new_status:
                Notification.objects.create(
                    recipient=updated_ticket.created_by,
                    actor=request.user,
                    ticket=updated_ticket,
                    message=f"#{updated_ticket.ticket_number} talebinizin durumu '{new_status}' olarak güncellendi."
                )

            # CANLI BİLDİRİM & E-POSTA: Atanan personel değiştiyse yeni personele bildir
            if updated_ticket.assigned_to and updated_ticket.assigned_to != old_assigned_user and updated_ticket.assigned_to != request.user:
                Notification.objects.create(
                    recipient=updated_ticket.assigned_to,
                    actor=request.user,
                    ticket=updated_ticket,
                    message=f"#{updated_ticket.ticket_number} talebi size atandı."
                )
                if updated_ticket.assigned_to.email:
                    send_notification_email(
                        subject=f"[Destek Talebi] #{updated_ticket.ticket_number} Talebi Size Atandı",
                        message=f"Merhaba {updated_ticket.assigned_to.username},\n\n#{updated_ticket.ticket_number} numaralı '{updated_ticket.title}' başlıklı destek talebi tarafınıza atanmıştır.\n\nDetayları incelemek için sisteme giriş yapabilirsiniz.",
                        recipient_list=[updated_ticket.assigned_to.email]
                    )

            # E-POSTA BİLDİRİMİ: Eğer durum değişmişse mail gönder
            if old_status != new_status and updated_ticket.created_by.email:
                send_notification_email(
                    subject=f"[Destek Talebi] #{updated_ticket.ticket_number} Durumu Güncellendi: {new_status}",
                    message=f"Merhaba {updated_ticket.created_by.username},\n\n#{updated_ticket.ticket_number} numaralı '{updated_ticket.title}' başlıklı talebinizin durumu '{old_status}' konumundan '{new_status}' konumuna güncellenmiştir.\n\nDetayları görüntülemek için sisteme giriş yapabilirsiniz.",
                    recipient_list=[updated_ticket.created_by.email]
                )
            if old_status != new_status:
                changes.append(f"Durum: '{old_status}' ➔ '{new_status}'")
            
            if old_assigned != new_assigned:
                changes.append(f"Atanan Yönetici: '{old_assigned}' ➔ '{new_assigned}'")
            if changes:
                for change in changes:
                    TicketActivityLog.objects.create(
                        ticket=updated_ticket,
                        actor=request.user,
                        action=change
                    )
            
            # Acil Durum Harici Webhook Tetikleyicisi
            if updated_ticket.priority == 'urgent':
                send_outgoing_webhook(updated_ticket, event_type="urgent_ticket_updated")

            messages.success(request, "Destek talebi başarıyla güncellendi.")
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        form = TicketForm(instance=ticket, user=request.user)

    context = {
        'form': form,
        'ticket': ticket,
    }
    return render(request, 'tickets/ticket_form.html', context)




@login_required
def ticket_delete(request, pk):
    """
    Destek talebi silme görünümü.
    - Süper yöneticiler tüm talepleri silebilir.
    - Personel yalnızca sorumlu olduğu departmanın taleplerini silebilir.
    - Standart kullanıcılar yalnızca kendi açtıkları ve henüz çözülmemiş/kapatılmamış talepleri silebilir.
    GET isteğinde onay sayfasını gösterir, POST isteğinde talebi kalıcı olarak siler.
    """
    ticket = get_object_or_404(Ticket, pk=pk)

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # Yetki Kontrolü:
    if not request.user.is_staff:
        # Standart kullanıcı kontrolü
        if ticket.created_by != request.user:
            messages.error(request, "Yalnızca kendi açtığınız destek taleplerini silebilirsiniz!")
            return redirect('ticket_list')
        if ticket.status in ['resolved', 'closed']:
            messages.error(request, "Çözülmüş veya kapatılmış destek talepleri silinemez!")
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        # Personel RBAC Departman İzolasyonu (Süper yönetici değilse başka birimin talebini silemez)
        if not is_superadmin and ticket.category:
            if profile and profile.assigned_categories.exists():
                if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                    messages.error(request, "Bu departman/kategoriye ait talepleri silme yetkiniz bulunmamaktadır!")
                    return redirect('ticket_list')

    if request.method == 'POST':
        ticket_title = ticket.title
        ticket.delete()
        messages.success(request, f"'{ticket_title}' başlıklı talep başarıyla silindi.")
        return redirect('ticket_list')
        
    context = {'ticket': ticket}
    return render(request, 'tickets/ticket_confirm_delete.html', context)





@login_required
def download_ticket_attachment(request, pk):
    """
    Talebe eklenen dosyayı yetki kontrolü yaparak güvenli bir şekilde sunar veya indirir.
    Gizli taleplerin doğrudan medya URL'si üzerinden yetkisiz indirilmesini engeller.
    """
    ticket = get_object_or_404(Ticket, pk=pk)

    if not ticket.attachment:
        raise Http404("Bu talebe ait ek dosya bulunamadı.")

    # Gizlilik ve RBAC Kontrolü
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    if not ticket.is_public and ticket.created_by != request.user and ticket.assigned_to != request.user and not is_superadmin:
        if not request.user.is_staff:
            return HttpResponseForbidden("Bu özel talebin ek dosyasını görüntüleme yetkiniz bulunmamaktadır.")
        elif profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                return HttpResponseForbidden("Bu departman/kategoriye ait ek dosyayı indirme yetkiniz bulunmamaktadır.")

    try:
        file_path = ticket.attachment.path
        if not os.path.exists(file_path):
            raise Http404("Dosya sunucu diskinde bulunamadı.")
    except (ValueError, NotImplementedError):
        file_path = None

    filename = ticket.attachment_filename or os.path.basename(ticket.attachment.name)
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or 'application/octet-stream'

    # Resim veya PDF ise tarayıcı içinde önizle (inline), download=1 veya diğer formatlarda indir (attachment)
    is_previewable = content_type.startswith('image/') or content_type == 'application/pdf'
    force_download = request.GET.get('download') == '1'
    as_attachment = force_download or (not is_previewable)

    if file_path:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type, as_attachment=as_attachment, filename=filename)
    else:
        response = FileResponse(ticket.attachment.open('rb'), content_type=content_type, as_attachment=as_attachment, filename=filename)

    return response




@login_required
def download_comment_attachment(request, comment_id):
    """
    Yorumlara eklenen dosyayı yetki kontrolü yaparak güvenli bir şekilde sunar veya indirir.
    İç notlara (is_internal) ait dosyaların normal kullanıcılarca erişilmesini engeller.
    """
    comment = get_object_or_404(TicketComment, id=comment_id)
    ticket = comment.ticket

    if not comment.attachment:
        raise Http404("Bu yoruma ait ek dosya bulunamadı.")

    # İç not eki kontrolü: Yalnızca yetkililer görebilir
    if comment.is_internal and not request.user.is_staff:
        return HttpResponseForbidden("Yöneticilere özel iç not dosyalarına erişim yetkiniz bulunmamaktadır.")

    # Talep Gizlilik ve RBAC Kontrolü
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    if not ticket.is_public and ticket.created_by != request.user and ticket.assigned_to != request.user and not is_superadmin:
        if not request.user.is_staff:
            return HttpResponseForbidden("Bu özel talebin yorum ekini görüntüleme yetkiniz bulunmamaktadır.")
        elif profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                return HttpResponseForbidden("Bu departman/kategoriye ait yorum ekini indirme yetkiniz bulunmamaktadır.")

    try:
        file_path = comment.attachment.path
        if not os.path.exists(file_path):
            raise Http404("Dosya sunucu diskinde bulunamadı.")
    except (ValueError, NotImplementedError):
        file_path = None

    filename = comment.attachment_filename or os.path.basename(comment.attachment.name)
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or 'application/octet-stream'

    is_previewable = content_type.startswith('image/') or content_type == 'application/pdf'
    force_download = request.GET.get('download') == '1'
    as_attachment = force_download or (not is_previewable)

    if file_path:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type, as_attachment=as_attachment, filename=filename)
    else:
        response = FileResponse(comment.attachment.open('rb'), content_type=content_type, as_attachment=as_attachment, filename=filename)

    return response


# --- RAPOR DIŞA AKTARMA (EXCEL / CSV EXPORT) ---

import csv
from django.http import HttpResponse



@login_required
@require_POST
def toggle_comment_solution(request, comment_id):
    """
    Bir yorumu En İyi Yanıt / Çözüm olarak işaretler veya işaretini kaldırır.
    İzin: Sadece talebi açan kullanıcı veya yöneticiler (is_staff) işlem yapabilir.
    CSRF korumalı POST istekleriyle çalışır.
    """
    comment = get_object_or_404(TicketComment, id=comment_id)
    ticket = comment.ticket
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.GET.get('ajax') == '1'

    # Yetki kontrolü: Yalnızca talebi açan veya yönetici işaretleyebilir
    if request.user != ticket.created_by and not request.user.is_staff:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Bu yorumu çözüm olarak işaretleme yetkiniz yok.'}, status=403)
        messages.error(request, "Bu yorumu çözüm olarak işaretleme yetkiniz yok.")
        return redirect('ticket_detail', pk=ticket.id)

    if comment.is_solution:
        comment.is_solution = False
        comment.save()
        msg = "Çözüm işareti kaldırıldı."
        # Geri alma: Başka çözüm yoksa ve talep çözüldü durumundaysa devam ediyor durumuna geri çek
        if ticket.status == 'resolved' and not ticket.comments.filter(is_solution=True).exists():
            ticket.status = 'in_progress'
            ticket.save(update_fields=['status', 'updated_at'])
            TicketActivityLog.objects.create(
                ticket=ticket,
                actor=request.user,
                action=f"Yorum (#{comment.id}) çözüm işareti geri alındı; talep 'Devam Ediyor' olarak güncellendi."
            )
        if not is_ajax:
            messages.info(request, msg)
    else:
        # Talebe ait tüm yorumların çözüm durumunu sıfırla (Her talepte tek onaylı çözüm)
        ticket.comments.update(is_solution=False)
        comment.is_solution = True
        comment.save()
        # Talebi otomatik olarak 'Çözüldü' yap
        if ticket.status != 'resolved':
            ticket.status = 'resolved'
            ticket.save(update_fields=['status', 'updated_at'])
            TicketActivityLog.objects.create(
                ticket=ticket,
                actor=request.user,
                action=f"Yorum (#{comment.id}) çözüm olarak onaylandı; talep 'Çözüldü' olarak işaretlendi."
            )
        msg = "Yorum 'En İyi Yanıt / Çözüm' olarak işaretlendi! ✅"
        if not is_ajax:
            messages.success(request, msg)

    has_solution = ticket.comments.filter(is_solution=True).exists()

    if is_ajax:
        return JsonResponse({
            'status': 'ok',
            'is_solution': comment.is_solution,
            'comment_id': comment.id,
            'has_solution': has_solution,
            'ticket_status': ticket.status,
            'ticket_status_display': ticket.get_status_display(),
            'message': msg
        })

    return redirect('ticket_detail', pk=ticket.id)




@login_required
@require_POST
def toggle_comment_like(request, comment_id):
    """
    Bir yorumu faydalı bulup beğenmeyi (upvote) veya beğeniyi kaldırmayı sağlar.
    CSRF korumalı POST istekleriyle çalışır.
    """
    comment = get_object_or_404(TicketComment, id=comment_id)
    ticket = comment.ticket
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.GET.get('ajax') == '1'

    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
        liked = False
        msg = "Yorum beğenisi kaldırıldı."
        if not is_ajax:
            messages.info(request, msg)
    else:
        comment.likes.add(request.user)
        liked = True
        msg = "Yorumu faydalı buldunuz! 👍"
        if not is_ajax:
            messages.success(request, msg)

    if is_ajax:
        return JsonResponse({
            'status': 'ok',
            'liked': liked,
            'like_count': comment.like_count,
            'comment_id': comment.id,
            'message': msg
        })

    return redirect('ticket_detail', pk=ticket.id)




@login_required
@require_POST
def comment_edit(request, comment_id):
    """
    Yorum sahibinin veya yetkililerin bir yorumu düzenlemesini sağlar.
    Hem standart POST hem de AJAX JSON isteklerini destekler.
    """
    comment = get_object_or_404(TicketComment, id=comment_id)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.GET.get('ajax') == '1'
    
    # Yetki kontrolü: Yorum sahibi, süper yönetici veya yetkili personel
    if request.user != comment.author and not request.user.is_staff and not request.user.is_superuser:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Bu yorumu düzenleme yetkiniz yok.'}, status=403)
        messages.error(request, "Bu yorumu düzenleme yetkiniz bulunmamaktadır.")
        return redirect('ticket_detail', pk=comment.ticket.pk)

    content = request.POST.get('content', '').strip()
    if not content:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Yorum metni boş bırakılamaz.'}, status=400)
        messages.error(request, "Yorum metni boş bırakılamaz.")
        return redirect('ticket_detail', pk=comment.ticket.pk)

    comment.content = content
    comment.save()

    TicketActivityLog.objects.create(
        ticket=comment.ticket,
        actor=request.user,
        action=f"#{comment.id} numaralı yorum düzenlendi."
    )

    if is_ajax:
        return JsonResponse({
            'status': 'ok',
            'comment_id': comment.id,
            'content': comment.content,
            'message': 'Yorum başarıyla güncellendi.'
        })

    messages.success(request, "Yorumunuz başarıyla güncellendi.")
    return redirect('ticket_detail', pk=comment.ticket.pk)




@login_required
@require_POST
def comment_delete(request, comment_id):
    """
    Yorum sahibinin veya yetkililerin yorumu silmesini sağlar.
    Ek dosyalar post_delete sinyaliyle diskten otomatik temizlenir.
    """
    comment = get_object_or_404(TicketComment, id=comment_id)
    ticket_pk = comment.ticket.pk
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.GET.get('ajax') == '1'

    if request.user != comment.author and not request.user.is_staff and not request.user.is_superuser:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Bu yorumu silme yetkiniz yok.'}, status=403)
        messages.error(request, "Bu yorumu silme yetkiniz bulunmamaktadır.")
        return redirect('ticket_detail', pk=ticket_pk)

    TicketActivityLog.objects.create(
        ticket=comment.ticket,
        actor=request.user,
        action=f"{comment.author.username} kullanıcısının bir yanıtı silindi."
    )
    comment.delete()

    if is_ajax:
        return JsonResponse({
            'status': 'ok',
            'comment_id': comment_id,
            'message': 'Yorum başarıyla silindi.'
        })

    messages.success(request, "Yorum başarıyla silindi.")
    return redirect('ticket_detail', pk=ticket_pk)


# --- BİLGİ BANKASI (KNOWLEDGE BASE / FAQ) GÖRÜNÜMLERİ ---



@login_required
@transaction.atomic
def bulk_ticket_action(request):
    """
    Talep listesinde seçilen birden fazla talep üzerinde toplu işlem uygular (Durum Değiştirme, Atama, Kategori).
    """
    if request.method != 'POST':
        return redirect('ticket_list')

    if not request.user.is_staff:
        messages.error(request, "Toplu işlem yapma yetkiniz bulunmamaktadır!")
        return redirect('ticket_list')

    selected_ids = request.POST.getlist('selected_tickets')
    action = request.POST.get('bulk_action', '').strip()
    target_value = request.POST.get('bulk_target_value', '').strip()

    if not selected_ids:
        messages.warning(request, "Lütfen işlem uygulamak için en az bir talep seçiniz.")
        return redirect('ticket_list')

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # Yetkili olunan talepleri filtrele
    tickets = Ticket.objects.filter(id__in=selected_ids)
    if not is_superadmin and profile and profile.assigned_categories.exists():
        tickets = tickets.filter(
            Q(category__in=profile.assigned_categories.all()) | Q(assigned_to=request.user)
        )

    updated_count = 0

    if action == 'status':
        valid_statuses = dict(Ticket.STATUS_CHOICES).keys()
        if target_value in valid_statuses:
            for t in tickets:
                old_status = t.get_status_display()
                t.status = target_value
                t.save(update_fields=['status', 'updated_at'])
                TicketActivityLog.objects.create(
                    ticket=t,
                    actor=request.user,
                    action=f"Toplu İşlem: Durum '{old_status}' ➔ '{t.get_status_display()}' olarak güncellendi."
                )
                updated_count += 1
            messages.success(request, f"{updated_count} adet talebin durumu başarıyla güncellendi.")
        else:
            messages.error(request, "Geçersiz durum seçimi.")

    elif action == 'assign':
        if not is_superadmin:
            messages.error(request, "Taleplere yetkili atama işlemini sadece Süper Yöneticiler gerçekleştirebilir!")
            return redirect('ticket_list')

        if target_value == 'unassign':
            for t in tickets:
                t.assigned_to = None
                t.save(update_fields=['assigned_to', 'updated_at'])
                TicketActivityLog.objects.create(
                    ticket=t,
                    actor=request.user,
                    action="Toplu İşlem: Atanan yönetici kaldırıldı."
                )
                updated_count += 1
            messages.success(request, f"{updated_count} adet talebin ataması kaldırıldı.")
        else:
            try:
                assignee = User.objects.get(id=int(target_value), is_staff=True)
                for t in tickets:
                    t.assigned_to = assignee
                    t.save(update_fields=['assigned_to', 'updated_at'])
                    TicketActivityLog.objects.create(
                        ticket=t,
                        actor=request.user,
                        action=f"Toplu İşlem: Talep {assignee.username} yöneticisine atandı."
                    )
                    if assignee != request.user:
                        Notification.objects.create(
                            recipient=assignee,
                            actor=request.user,
                            ticket=t,
                            message=f"#{t.ticket_number} talebi size atandı."
                        )
                    updated_count += 1
                if assignee != request.user and assignee.email and updated_count > 0:
                    send_notification_email(
                        subject=f"[Destek Talebi] Size {updated_count} Adet Talep Atandı",
                        message=f"Merhaba {assignee.username},\n\nSistem üzerinden tarafınıza {updated_count} adet yeni destek talebi atanmıştır.\n\nTalepleri incelemek için sisteme giriş yapabilirsiniz.",
                        recipient_list=[assignee.email]
                    )
                messages.success(request, f"{updated_count} adet talep {assignee.username} yöneticisine atandı.")
            except (ValueError, User.DoesNotExist):
                messages.error(request, "Seçilen yönetici bulunamadı.")

    elif action == 'category':
        try:
            new_cat = Category.objects.get(id=int(target_value))
            for t in tickets:
                old_cat_name = t.category.name if t.category else "Kategorisiz"
                t.category = new_cat
                t.save(update_fields=['category', 'updated_at'])
                TicketActivityLog.objects.create(
                    ticket=t,
                    actor=request.user,
                    action=f"Toplu İşlem: Kategori '{old_cat_name}' ➔ '{new_cat.name}' olarak değiştirildi."
                )
                updated_count += 1
            messages.success(request, f"{updated_count} adet talebin kategorisi güncellendi.")
        except (ValueError, Category.DoesNotExist):
            messages.error(request, "Seçilen kategori bulunamadı.")

    elif action == 'merge':
        if tickets.count() < 2:
            messages.warning(request, "Birleştirme işlemi için en az 2 adet talep seçmelisiniz.")
            return redirect('ticket_list')

        tickets_list = list(tickets.order_by('created_at'))
        primary_ticket = tickets_list[0]
        merged_count = 0

        for sec in tickets_list[1:]:
            sec.merged_into = primary_ticket
            sec.status = 'closed'
            sec.save(update_fields=['merged_into', 'status', 'updated_at'])
            for tg in sec.tags.all():
                primary_ticket.tags.add(tg)
            TicketComment.objects.create(
                ticket=sec,
                author=request.user,
                content=f"🔒 Bu talep, #{primary_ticket.ticket_number} numaralı ana talep ile birleştirilerek kapatılmıştır."
            )
            TicketComment.objects.create(
                ticket=primary_ticket,
                author=request.user,
                content=f"🔗 #{sec.ticket_number} ('{sec.title}') yinelenen talebi bu talep ile birleştirildi.",
                is_internal=True
            )
            TicketActivityLog.objects.create(
                ticket=primary_ticket,
                actor=request.user,
                action=f"Toplu Birleştirme: #{sec.ticket_number} talebi bu talep ile birleştirildi."
            )
            merged_count += 1

        messages.success(request, f"{merged_count} adet talep başarıyla #{primary_ticket.ticket_number} ana talebine birleştirildi.")
        return redirect('ticket_detail', pk=primary_ticket.pk)

    else:
        messages.warning(request, "Geçersiz işlem seçildi.")

    return redirect('ticket_list')




@login_required
@require_POST
@transaction.atomic
def merge_tickets_view(request):
    """
    Talep detay sayfasından iki talebi birleştirir (Merge Tickets).
    İkincil talep kapatılır ve içeriği/geçmişi ana talebe aktarılır.
    Yalnızca yetkili personel (is_staff) yapabilir.
    """
    if not request.user.is_staff:
        messages.error(request, "Talep birleştirme yetkiniz bulunmamaktadır.")
        return redirect('ticket_list')

    primary_id = request.POST.get('primary_ticket_id')
    secondary_id = request.POST.get('secondary_ticket_id')

    if not primary_id or not secondary_id:
        messages.error(request, "Birleştirme için iki talep de belirlenmelidir.")
        return redirect('ticket_list')

    if str(primary_id) == str(secondary_id):
        messages.error(request, "Bir talep kendisiyle birleştirilemez.")
        return redirect('ticket_detail', pk=primary_id)

    primary_ticket = get_object_or_404(Ticket, id=primary_id)
    secondary_ticket = get_object_or_404(Ticket, id=secondary_id)

    secondary_ticket.merged_into = primary_ticket
    secondary_ticket.status = 'closed'
    secondary_ticket.save(update_fields=['merged_into', 'status', 'updated_at'])

    for tg in secondary_ticket.tags.all():
        primary_ticket.tags.add(tg)

    TicketComment.objects.create(
        ticket=secondary_ticket,
        author=request.user,
        content=f"🔒 Bu talep, #{primary_ticket.ticket_number} ('{primary_ticket.title}') numaralı ana talep ile birleştirilerek kapatılmıştır."
    )
    TicketComment.objects.create(
        ticket=primary_ticket,
        author=request.user,
        content=f"🔗 #{secondary_ticket.ticket_number} ('{secondary_ticket.title}') yinelenen talebi bu talep ile birleştirildi.",
        is_internal=True
    )
    TicketActivityLog.objects.create(
        ticket=primary_ticket,
        actor=request.user,
        action=f"#{secondary_ticket.ticket_number} talebi bu talep ile birleştirildi."
    )
    TicketActivityLog.objects.create(
        ticket=secondary_ticket,
        actor=request.user,
        action=f"Bu talep #{primary_ticket.ticket_number} ana talebiyle birleştirildi ve kapatıldı."
    )

    messages.success(request, f"#{secondary_ticket.ticket_number} talebi başarıyla #{primary_ticket.ticket_number} ana talebine birleştirildi.")
    return redirect('ticket_detail', pk=primary_ticket.pk)



# ==========================================
# 2FA (İKİ AŞAMALI DOĞRULAMA - TOTP) GÖRÜNÜMLERİ
# ==========================================


