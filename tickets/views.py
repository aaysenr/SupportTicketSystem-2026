import os
import mimetypes
import json
import re
import threading
import logging
import nh3
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, FileResponse, HttpResponseForbidden, Http404
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash 
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, Count, Avg, F
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.utils import timezone

from .models import (
    Ticket, TicketComment, Category, EmailVerification, TicketActivityLog,
    Notification, ChatGroup, ChatMessage, UserProfile, KnowledgeBaseArticle,
    TicketRating, CannedResponse
)
from .forms import TicketForm, CommentForm, UserRegisterForm, UserProfileForm
from .totp import (
    generate_totp_secret, get_totp_token, verify_totp_token,
    get_totp_uri, generate_qr_code_data_uri
)
from .pdf import generate_ticket_pdf
from .webhooks import send_outgoing_webhook
from .copilot import suggest_category_and_priority, generate_ticket_summary

logger = logging.getLogger(__name__)

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

    # RBAC Kapsam Belirleme: Süper yönetici tüm talepleri, personel sadece kendi birimini görür
    if is_superadmin:
        base_qs = Ticket.objects.all()
        categories = Category.objects.annotate(ticket_count=Count('tickets'))
    elif profile and profile.assigned_categories.exists():
        allowed_cats = profile.assigned_categories.all()
        base_qs = Ticket.objects.filter(
            Q(category__in=allowed_cats) | Q(assigned_to=request.user)
        ).distinct()
        categories = allowed_cats.annotate(ticket_count=Count('tickets'))
    else:
        base_qs = Ticket.objects.all()
        categories = Category.objects.annotate(ticket_count=Count('tickets'))

    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. Tekil SQL Koşullu Toplama (Conditional Aggregation) ile Tüm Metrikler (N+1 Sorgu Engellendi)
    metrics = base_qs.aggregate(
        total_tickets=Count('id'),
        open_tickets=Count('id', filter=Q(status='open')),
        in_progress_tickets=Count('id', filter=Q(status='in_progress')),
        resolved_tickets=Count('id', filter=Q(status='resolved')),
        urgent_tickets=Count('id', filter=Q(priority='urgent')),
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
    urgent_tickets = metrics['urgent_tickets']
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

    # 4. Kategori Dağılımı Verileri (Chart.js İçin)
    category_labels = [cat.name for cat in categories]
    category_counts = [cat.ticket_count for cat in categories]

    # 5. Öncelik Dağılımı Verileri
    priority_data = {
        'Düşük': metrics['priority_low'],
        'Orta': metrics['priority_medium'],
        'Yüksek': metrics['priority_high'],
        'Acil': metrics['priority_urgent'],
    }

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
        
        # Chart.js'in JSON formatında okuyabilmesi için:
        'category_labels_json': json.dumps(category_labels),
        'category_counts_json': json.dumps(category_counts),
        'priority_labels_json': json.dumps(list(priority_data.keys())),
        'priority_counts_json': json.dumps(list(priority_data.values())),
    }

    return render(request, 'tickets/dashboard.html', context)



def verify_email(request):
    user_id = request.session.get('unverified_user_id')
    if not user_id:
        return redirect('register')
    
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        # Kodu Tekrar Gönder (Resend OTP)
        if action == 'resend':
            verification, _ = EmailVerification.objects.get_or_create(user=user)
            verification.generate_code()
            try:
                send_mail(
                    subject="E-Posta Dogrulama Kodu (Tekrar)",
                    message=f"Merhaba {user.username},\n\nYeni dogrulama kodunuz: {verification.code}\n\nBu kod 10 dakika süreyle geçerlidir.",
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=True
                )
                messages.success(request, f"Yeni doğrulama kodu {user.email} adresine gönderildi.")
            except Exception:
                messages.warning(request, "E-posta servisine erişilemedi ancak yeni kod üretildi.")
            return redirect('verify_email')

        entered_code = request.POST.get('code', '').strip()
        try:
            verification = user.email_verification
            if verification.failed_attempts >= 5:
                messages.error(request, "Çok fazla hatalı deneme yaptınız. Güvenliğiniz için bu kod iptal edildi. Lütfen 'Yeni Kod Gönder' butonunu kullanın.")
            elif verification.code == entered_code and verification.is_valid():
                # Kod doğru ve süresi geçerli!
                user.is_active = True
                user.save()
                
                # Oturumu temizle ve otomatik giriş yaptır
                del request.session['unverified_user_id']
                login(request, user)
                messages.success(request, f"Tebrikler {user.username}! E-postanız başarıyla doğrulandı ve hesabınız aktifleştirildi.")
                return redirect('ticket_list')
            else:
                verification.failed_attempts += 1
                verification.save(update_fields=['failed_attempts'])
                remaining = max(0, 5 - verification.failed_attempts)
                if remaining > 0:
                    messages.error(request, f"Girdiğiniz doğrulama kodu hatalı veya süresi dolmuş! (Kalan deneme hakkı: {remaining})")
                else:
                    messages.error(request, "5 hatalı deneme hakkınız doldu. Lütfen 'Yeni Kod Gönder' butonunu kullanarak yeni kod talep edin.")
        except EmailVerification.DoesNotExist:
            messages.error(request, "Doğrulama bilgisi bulunamadı.")

    return render(request, 'tickets/verify_email.html', {'user': user})



# --- 1. KULLANICI OTURUM GÖRÜNÜMLERİ (AUTH VIEWS) ---

def register_user(request):
    """
    Yeni kullanıcı kayıt görünümü.
    Eğer kullanıcı zaten giriş yapmışsa direkt liste sayfasına yönlendirir.
    """
    if request.user.is_authenticated:
        return redirect('ticket_list')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # 1. Kullanıcıyı henüz pasif (is_active=False) olarak kaydediyoruz
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # 2. Onay kodu oluşturuyoruz
            verification, created = EmailVerification.objects.get_or_create(user=user)
            verification.generate_code()

            # 3. E-posta gönderiyoruz (SMTP bağlantı hatasına karşı korumalı)
            try:
                send_mail(
                    subject="E-Posta Dogrulama Kodu",
                    message=f"Merhaba {user.username},\n\nDestek Sistemine kayit isleminizi tamamlamak için dogrulama kodunuz: {verification.code}\n\nBu kod 10 dakika süreyle gecerlidir.",
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=True
                )
            except Exception:
                pass

            # 4. Kullanıcı ID'sini oturuma kaydedip doğrulama sayfasına yönlendiriyoruz
            request.session['unverified_user_id'] = user.id
            messages.info(request, "Lütfen e-posta adresinize gönderilen 6 haneli doğrulama kodunu girin.")
            return redirect('verify_email')
        else:
            messages.error(request, "Lütfen formdaki hataları düzeltin.")
    else:
        form = UserRegisterForm()

    context = {'form': form}
    return render(request, 'tickets/register.html', context) 



def login_user(request):
    """
    Kullanıcı giriş görünümü. ?next= yönlendirmesini destekler ve onaylanmamış hesapları doğrulama sayfasına aktarır.
    """
    if request.user.is_authenticated:
        return redirect('ticket_list')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                profile = getattr(user, 'profile', None)
                if profile and profile.is_2fa_enabled and profile.totp_secret:
                    request.session['2fa_user_id'] = user.id
                    request.session['2fa_next'] = request.POST.get('next') or request.GET.get('next') or ''
                    return redirect('verify_2fa')

                login(request, user)
                messages.success(request, f"Tekrar hoş geldiniz, {username}!")
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect('ticket_list')
            else:
                messages.error(request, "Kullanıcı adı veya parola hatalı.")
        else:
            # Kullanıcı adı ve şifre doğru ama hesap henüz doğrulanmamış (is_active=False) olabilir
            username_input = request.POST.get('username')
            password_input = request.POST.get('password')
            if username_input and password_input:
                unverified_user = User.objects.filter(username=username_input, is_active=False).first()
                if unverified_user and unverified_user.check_password(password_input):
                    request.session['unverified_user_id'] = unverified_user.id
                    messages.info(request, "Hesabınız henüz doğrulanmamış. Lütfen doğrulama kodunu giriniz.")
                    return redirect('verify_email')
            messages.error(request, "Geçersiz giriş bilgileri.")
    else:
        form = AuthenticationForm()

    context = {
        'form': form,
        'next': request.GET.get('next', '')
    }
    return render(request, 'tickets/login.html', context)



def logout_user(request):
    """
    Kullanıcı oturum kapatma görünümü.
    """
    logout(request)
    messages.info(request, "Başarıyla çıkış yaptınız.")
    return redirect('login')


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
    tickets = base_tickets.annotate(comment_count=Count('comments'))
    
    search_query = request.GET.get('q', '').strip()
    selected_status = request.GET.get('status', '').strip()
    selected_priority = request.GET.get('priority', '').strip()
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
def profile_view(request):
    """
    Kullanıcı profil bilgilerini görüntüleme ve güncelleme ekranı.
    """
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil bilgileriniz başarıyla güncellendi.")
            return redirect('profile')
        else:
            messages.error(request, "Lütfen formdaki hataları düzeltin.")
    else:
        form = UserProfileForm(instance=request.user, user=request.user)
    
    return render(request, 'tickets/profile.html', {'form': form})


@login_required
def change_password_view(request):
    """
    Güvenli Şifre Değiştirme Ekranı.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Şifre değiştiğinde kullanıcının oturumunun kapanmasını engeller:
            update_session_auth_hash(request, user)
            messages.success(request, "Şifreniz başarıyla değiştirildi!")
            return redirect('profile')
        else:
            messages.error(request, "Lütfen şifre değiştirme formundaki hataları düzeltin.")
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'tickets/change_password.html', {'form': form})



def _async_email_worker(subject, message, recipient_list, html_message=None):
    try:
        from django.conf import settings
        valid_recipients = [email for email in recipient_list if email]
        if valid_recipients:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=valid_recipients,
                html_message=html_message,
                fail_silently=False
            )
            logger.info("[E-POSTA] E-posta başarıyla gönderildi: Konu='%s'", subject)
    except Exception as exc:
        logger.error("[E-POSTA] E-posta gönderiminde hata: %s", exc)


def send_notification_email(subject, message, recipient_list, ticket=None, action_url=None, html_message=None):
    """
    Güvenli, Markalı (HTML) ve Asenkron (Non-blocking) E-posta Bildirim Gönderici.
    Ana HTTP istek döngüsünü bloke etmeden arka planda zengin HTML e-posta gönderir.
    """
    if recipient_list and any(recipient_list):
        if not html_message:
            try:
                from django.template.loader import render_to_string
                html_message = render_to_string('emails/ticket_notification_email.html', {
                    'subject': subject,
                    'message': message,
                    'ticket': ticket,
                    'action_url': action_url,
                })
            except Exception as e:
                logger.warning("[E-POSTA] HTML şablonu derlenemedi, düz metin ile devam ediliyor: %s", e)
                html_message = None

        recipients = ", ".join([e for e in recipient_list if e])
        logger.info("[E-POSTA] Bildirim e-postası kuyruğa alındı: Alıcı(lar)=%s, Konu='%s'", recipients, subject)

        worker_thread = threading.Thread(
            target=_async_email_worker,
            args=(subject, message, recipient_list, html_message),
            daemon=True
        )
        worker_thread.start()






@login_required
def notifications_list_view(request):
    notifications = Notification.objects.filter(recipient=request.user)
    return render(request, 'tickets/notifications.html', {'notifications': notifications})

@login_required
def mark_notification_as_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    if notification.ticket:
        return redirect('ticket_detail', pk=notification.ticket.pk)
    return redirect('notifications_list')


@login_required
def mark_all_notifications_as_read(request):
    """
    Kullanıcının tüm okunmamış bildirimlerini tek tıkla okundu olarak işaretler.
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "Tüm bildirimleriniz başarıyla okundu olarak işaretlendi.")
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'notifications_list'
    return redirect(next_url)

   

@login_required
def team_chat_view(request, chat_type='group', chat_id=None):
    """
    Yöneticiler için Ekip Sohbeti, Özel Gruplar ve DM Arayüzü.
    """
    # 🔒 Güvenlik Kontrolü: Yalnızca yöneticiler erişebilir!
    if not request.user.is_staff:
        messages.error(request, "Ekip sohbetine yalnızca yetkili yöneticiler erişebilir!")
        return redirect('ticket_list')

    # 1. Varsayılan "Genel Ekip Odası" yoksa otomatik oluştur
    general_group, _ = ChatGroup.objects.get_or_create(
        is_general=True,
        defaults={'name': 'Genel Ekip Odası', 'created_by': request.user}
    )
    if request.user not in general_group.members.all():
        general_group.members.add(request.user)

    # 2. Tüm Yöneticileri ve Üzerlerindeki Aktif Talep Sayısını Çek
    managers = User.objects.filter(is_staff=True).annotate(
        active_tickets_count=Count(
            'assigned_tickets',
            filter=Q(assigned_tickets__status__in=['open', 'in_progress'])
        )
    )

    # 3. Giriş yapan yöneticinin dahil olduğu Özel Gruplar
    user_groups = ChatGroup.objects.filter(members=request.user, is_general=False)

    # 4. Aktif Sohbet Kanalını Belirle
    active_channel = {
        'type': chat_type,
        'id': chat_id,
        'title': 'Genel Ekip Odası',
        'target_user': None,
        'group': general_group
    }

    messages_list = []

    if chat_type == 'dm' and chat_id:
        recipient = get_object_or_404(User, id=chat_id, is_staff=True)
        active_channel['title'] = f"💬 {recipient.get_full_name() or recipient.username}"
        active_channel['target_user'] = recipient
        # İki kullanıcı arasındaki özel mesajlar (DM)
        messages_list = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=recipient) |
            Q(sender=recipient, recipient=request.user)
        ).order_by('created_at')

    elif chat_type == 'group' and chat_id:
        group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
        active_channel['title'] = f"👥 {group.name}"
        active_channel['group'] = group
        messages_list = group.messages.all().order_by('created_at')

    else:
        # Varsayılan: Genel Ekip Odası
        active_channel['type'] = 'group'
        active_channel['id'] = general_group.id
        messages_list = general_group.messages.all().order_by('created_at')

    context = {
        'managers': managers,
        'general_group': general_group,
        'user_groups': user_groups,
        'active_channel': active_channel,
        'chat_messages': messages_list,
    }

    return render(request, 'tickets/team_chat.html', context)


@login_required
def send_chat_message_view(request):
    """
    Sohbet Mesajı Gönderme Endpoint'i (AJAX & Form Uyumlu)
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim'}, status=403)

    if request.method == 'POST':
        chat_type = request.POST.get('chat_type')
        chat_id = request.POST.get('chat_id')
        content = request.POST.get('content', '').strip()

        if not content:
            return JsonResponse({'status': 'error', 'message': 'Mesaj boş olamaz'}, status=400)

        msg = None
        if chat_type == 'dm':
            recipient = get_object_or_404(User, id=chat_id, is_staff=True)
            msg = ChatMessage.objects.create(sender=request.user, recipient=recipient, content=content)
        else:
            group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
            msg = ChatMessage.objects.create(sender=request.user, group=group, content=content)

        # WebSocket kullanıcılarına anlık yayınla (Channel Layer Broadcast)
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                if chat_type == 'dm':
                    u1, u2 = sorted([request.user.id, recipient.id])
                    room_group = f"chat_dm_{u1}_{u2}"
                else:
                    room_group = f"chat_group_{group.id}"
                
                async_to_sync(channel_layer.group_send)(
                    room_group,
                    {
                        "type": "chat_message_broadcast",
                        "message_id": msg.id,
                        "sender_id": msg.sender.id,
                        "sender_name": msg.sender.get_full_name() or msg.sender.username,
                        "content": msg.content,
                        "created_at": msg.created_at.strftime('%H:%M')
                    }
                )
        except Exception:
            pass

        return JsonResponse({
            'status': 'success',
            'message_id': msg.id,
            'sender_id': msg.sender.id,
            'sender_name': msg.sender.get_full_name() or msg.sender.username,
            'content': msg.content,
            'created_at': msg.created_at.strftime('%H:%M')
        })

    return JsonResponse({'status': 'error', 'message': 'Geçersiz istek'}, status=400)


@login_required
def create_chat_group_view(request):
    """
    Yeni Özel Sohbet Grubu Oluşturma
    """
    if not request.user.is_staff:
        messages.error(request, "Yetkiniz yok!")
        return redirect('ticket_list')

    if request.method == 'POST':
        group_name = request.POST.get('group_name', '').strip()
        member_ids = request.POST.getlist('members')

        if group_name:
            group = ChatGroup.objects.create(name=group_name, created_by=request.user)
            # Kurucuyu gruba ekle
            group.members.add(request.user)
            # Seçilen diğer yöneticileri ekle
            if member_ids:
                selected_members = User.objects.filter(id__in=member_ids, is_staff=True)
                group.members.add(*selected_members)

            messages.success(request, f"'{group_name}' sohbet grubu oluşturuldu.")
            return redirect('team_chat_detail', chat_type='group', chat_id=group.id)

    return redirect('team_chat')


@login_required
def get_chat_messages_api(request, chat_type, chat_id):
    """
    Canlı Sohbet Yenileme İçin Mesajları JSON Dönen API.
    ?after_id=<id> parametresi verildiğinde yalnızca o ID'den sonraki yeni mesajları döner.
    """
    if not request.user.is_staff:
        return JsonResponse({'messages': []}, status=403)

    after_id = request.GET.get('after_id')

    if chat_type == 'dm':
        recipient = get_object_or_404(User, id=chat_id, is_staff=True)
        messages_qs = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=recipient) |
            Q(sender=recipient, recipient=request.user)
        )
    else:
        group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
        messages_qs = group.messages.all()

    if after_id and after_id.isdigit():
        messages_qs = messages_qs.filter(id__gt=int(after_id))

    messages_qs = messages_qs.order_by('created_at')

    data = []
    for m in messages_qs:
        data.append({
            'message_id': m.id,
            'sender_id': m.sender.id,
            'sender_name': m.sender.get_full_name() or m.sender.username,
            'content': m.content,
            'created_at': m.created_at.strftime('%H:%M')
        })

    return JsonResponse({'messages': data})


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

def knowledge_base_list_view(request):
    """
    Sıkça sorulan sorular (SSS) ve Bilgi Bankası makale listesi.
    Dinamik Category modeli üzerinden kategori bazlı filtreleme ve sayaç sunar.
    """
    q = request.GET.get('q', '').strip()
    selected_category = request.GET.get('category', '').strip()

    articles = KnowledgeBaseArticle.objects.filter(is_published=True).select_related('category')

    if q:
        articles = articles.filter(
            Q(title__icontains=q) | 
            Q(content__icontains=q) | 
            Q(keywords__icontains=q)
        )

    if selected_category:
        if selected_category.isdigit():
            articles = articles.filter(category_id=int(selected_category))
        else:
            articles = articles.filter(category__name__icontains=selected_category)

    # Dinamik Kategori istatistikleri (Yayınlanmış makalesi olan kategoriler)
    categories = Category.objects.annotate(
        article_count=Count('kb_articles', filter=Q(kb_articles__is_published=True))
    ).filter(article_count__gt=0).order_by('name')

    categories_stats = [
        {
            'code': str(cat.id),
            'id': cat.id,
            'name': cat.name,
            'count': cat.article_count,
        }
        for cat in categories
    ]

    paginator = Paginator(articles, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'articles': page_obj,
        'categories_stats': categories_stats,
        'search_query': q,
        'selected_category': selected_category,
    }
    return render(request, 'tickets/knowledge_base.html', context)


def knowledge_base_detail_view(request, pk):
    """
    Tek bir Bilgi Bankası makalesinin detay sayfası.
    """
    article = get_object_or_404(KnowledgeBaseArticle.objects.select_related('category'), pk=pk, is_published=True)
    # Görüntülenme sayacını atomik olarak artır (Race condition engellendi)
    KnowledgeBaseArticle.objects.filter(pk=pk).update(views_count=F('views_count') + 1)
    article.refresh_from_db(fields=['views_count'])

    # Benzer / İlgili makaleler
    if article.category:
        related_articles = KnowledgeBaseArticle.objects.filter(
            is_published=True, category=article.category
        ).exclude(pk=article.pk)[:4]
    else:
        related_articles = KnowledgeBaseArticle.objects.filter(
            is_published=True
        ).exclude(pk=article.pk)[:4]

    context = {
        'article': article,
        'related_articles': related_articles,
    }
    return render(request, 'tickets/knowledge_base_detail.html', context)


def kb_suggest_api(request):
    """
    Yeni talep formunda kullanıcının yazdığı başlığa göre canlı SSS ve benzer çözülmüş talep önerisi sunan AJAX API'si.
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({'suggestions': []})

    suggestions = []

    # 1. Bilgi Bankası Makaleleri
    kb_qs = KnowledgeBaseArticle.objects.filter(
        is_published=True
    ).select_related('category').filter(
        Q(title__icontains=q) | Q(keywords__icontains=q) | Q(content__icontains=q)
    )[:4]

    for item in kb_qs:
        suggestions.append({
            'id': item.id,
            'title': item.title,
            'category': item.category.name if item.category else 'Genel',
            'snippet': (item.content[:120] + '...') if len(item.content) > 120 else item.content,
            'url': f"/knowledge-base/{item.id}/",
            'type': 'kb',
            'type_display': '📚 Bilgi Bankası Makalesi'
        })

    # 2. Herkese Açık ve Çözülmüş Benzer Talepler
    resolved_tickets = Ticket.objects.filter(
        is_public=True,
        status='resolved'
    ).filter(
        Q(title__icontains=q) | Q(description__icontains=q)
    ).select_related('category')[:3]

    for t in resolved_tickets:
        suggestions.append({
            'id': t.id,
            'title': t.title,
            'category': t.category.name if t.category else "Genel",
            'snippet': (t.description[:120] + '...') if len(t.description) > 120 else t.description,
            'url': f"/ticket/{t.id}/",
            'type': 'ticket',
            'type_display': '✅ Çözülmüş Topluluk Talebi'
        })

    return JsonResponse({'suggestions': suggestions})


@login_required
def submit_ticket_rating_api(request, ticket_id):
    """
    Çözülmüş bir destek talebi için müşteri memnuniyeti (CSAT) puanı ve görüşü kaydetme API'si.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Sadece POST isteği kabul edilir.'}, status=405)

    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Sadece talep sahibi veya süper yönetici değerlendirebilir
    if ticket.created_by != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Yalnızca talep sahibi değerlendirme yapabilir.'}, status=403)

    if ticket.status != 'resolved':
        return JsonResponse({'status': 'error', 'message': 'Sadece çözüldü durumundaki talepler değerlendirilebilir.'}, status=400)

    try:
        score = int(request.POST.get('score', 5))
        if score < 1 or score > 5:
            score = 5
    except (ValueError, TypeError):
        score = 5

    feedback = request.POST.get('feedback', '').strip()

    rating, created = TicketRating.objects.update_or_create(
        ticket=ticket,
        defaults={
            'user': request.user,
            'score': score,
            'feedback': feedback,
        }
    )

    return JsonResponse({
        'status': 'ok',
        'score': rating.score,
        'feedback': rating.feedback,
        'message': 'Geri bildiriminiz ve puanınız başarıyla kaydedildi. Teşekkür ederiz! ⭐'
    })


# --- GÜVENLİ DOSYA İNDİRME VE AKIŞ GÖRÜNÜMLERİ (SECURE ATTACHMENTS) ---

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
def export_tickets_csv(request):
    """
    Destek taleplerini Excel uyumlu CSV (UTF-8 BOM ve ';' ayracı) formatında dışa aktarır.
    Aktif filtreleri ve RBAC departman yetkilendirmesini uygular.
    """
    if not request.user.is_staff:
        messages.error(request, "Rapor dışa aktarma yetkiniz bulunmamaktadır!")
        return redirect('ticket_list')

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # 1. RBAC Kapsamı
    if is_superadmin:
        base_qs = Ticket.objects.all()
    elif profile and profile.assigned_categories.exists():
        allowed_cats = profile.assigned_categories.all()
        base_qs = Ticket.objects.filter(
            Q(category__in=allowed_cats) | Q(assigned_to=request.user)
        ).distinct()
    else:
        base_qs = Ticket.objects.all()

    # 2. Filtre Parametreleri
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    priority = request.GET.get('priority', '').strip()
    category_id = request.GET.get('category', '').strip()
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
    if mine:
        tickets = tickets.filter(created_by=request.user)

    tickets = tickets.select_related('created_by', 'category', 'assigned_to').prefetch_related('comments').order_by('-created_at')

    # 3. CSV Yanıtı (Windows Excel Türkçe karakter uyumu için utf-8-sig ve ';' ayracı)
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"destek_talepleri_raporu_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Talep No', 'Başlık', 'Kategori', 'Öncelik', 'Durum',
        'Oluşturan', 'Atanan Yönetici', 'Gizlilik', 'Oluşturulma Tarihi',
        'Son Güncelleme', 'İlk Yanıt Tarihi', 'SLA Durumu', 'Yorum Sayısı'
    ])

    for t in tickets:
        sla_text = "SLA Aşıldı" if t.is_sla_breached else ("İlk Yanıt Verildi" if t.first_response_at else "Zamanında Devam Ediyor")
        writer.writerow([
            t.ticket_number,
            t.title,
            t.category.name if t.category else "Kategorisiz",
            t.get_priority_display(),
            t.get_status_display(),
            t.created_by.username,
            t.assigned_to.username if t.assigned_to else "Atanmadı",
            "Herkese Açık" if t.is_public else "Özel / Gizli",
            t.created_at.strftime('%d.%m.%Y %H:%M') if t.created_at else "",
            t.updated_at.strftime('%d.%m.%Y %H:%M') if t.updated_at else "",
            t.first_response_at.strftime('%d.%m.%Y %H:%M') if t.first_response_at else "Henüz Yanıtlanmadı",
            sla_text,
            t.comments.count()
        ])

    return response


# --- TOPLU İŞLEMLER (BULK ACTIONS) ---

@login_required
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
    else:
        messages.warning(request, "Geçersiz işlem seçildi.")

    return redirect('ticket_list')


# ==========================================
# 2FA (İKİ AŞAMALI DOĞRULAMA - TOTP) GÖRÜNÜMLERİ
# ==========================================

@login_required
def setup_2fa_view(request):
    """
    Kullanıcıya Google Authenticator / Authy uyumlu 2FA kurulumu sunar.
    QR kod ve manuel gizli anahtarı gösterir, kullanıcının girdiği kodu doğrulayarak aktifleştirir.
    """
    profile = getattr(request.user, 'profile', None)
    if not profile:
        profile = UserProfile.objects.create(user=request.user)

    if profile.is_2fa_enabled:
        messages.info(request, "İki Aşamalı Doğrulama (2FA) hesabınızda zaten aktif.")
        return redirect('profile')

    # Session'da bekleyen gizli anahtar varsa al, yoksa yeni üret
    pending_secret = request.session.get('pending_totp_secret')
    if not pending_secret:
        pending_secret = generate_totp_secret()
        request.session['pending_totp_secret'] = pending_secret

    totp_uri = get_totp_uri(pending_secret, request.user.username)
    qr_data_uri = generate_qr_code_data_uri(totp_uri)

    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        if verify_totp_token(pending_secret, token):
            profile.totp_secret = pending_secret
            profile.is_2fa_enabled = True
            profile.save(update_fields=['totp_secret', 'is_2fa_enabled'])
            if 'pending_totp_secret' in request.session:
                del request.session['pending_totp_secret']
            messages.success(request, "Tebrikler! İki Aşamalı Doğrulama (2FA) başarıyla etkinleştirildi.")
            return redirect('profile')
        else:
            messages.error(request, "Girilen 6 haneli doğrulama kodu hatalı. Lütfen uygulamanızdaki güncel kodu giriniz.")

    context = {
        'secret': pending_secret,
        'qr_data_uri': qr_data_uri,
        'totp_uri': totp_uri,
    }
    return render(request, 'tickets/setup_2fa.html', context)


@login_required
@require_POST
def disable_2fa_view(request):
    """
    Kullanıcının 2FA korumasını mevcut şifresini onaylatarak devre dışı bırakır.
    """
    password = request.POST.get('password', '').strip()
    if not request.user.check_password(password):
        messages.error(request, "2FA'yı kapatmak için hesap şifrenizi doğru girmelisiniz.")
        return redirect('profile')

    profile = getattr(request.user, 'profile', None)
    if profile:
        profile.is_2fa_enabled = False
        profile.totp_secret = ""
        profile.save(update_fields=['is_2fa_enabled', 'totp_secret'])
        messages.success(request, "İki Aşamalı Doğrulama (2FA) başarıyla devre dışı bırakıldı.")

    return redirect('profile')


def verify_2fa_view(request):
    """
    2FA aktif kullanıcıların şifre doğrulamasından sonra 6 haneli kodu girdiği ara doğrulama görünümü.
    """
    user_id = request.session.get('2fa_user_id')
    if not user_id:
        return redirect('login')

    user = get_object_or_404(User, id=user_id)
    profile = getattr(user, 'profile', None)
    if not profile or not profile.is_2fa_enabled or not profile.totp_secret:
        # 2FA gereksinimi yoksa oturum açtır
        login(request, user)
        if '2fa_user_id' in request.session:
            del request.session['2fa_user_id']
        return redirect('ticket_list')

    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        if verify_totp_token(profile.totp_secret, token):
            login(request, user)
            next_url = request.session.pop('2fa_next', None)
            if '2fa_user_id' in request.session:
                del request.session['2fa_user_id']
            messages.success(request, f"İki aşamalı doğrulama başarılı! Tekrar hoş geldiniz, {user.username}.")
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('ticket_list')
        else:
            messages.error(request, "Doğrulama kodu hatalı veya süresi geçmiş. Lütfen Authenticator uygulamanızı kontrol edin.")

    # Kullanıcı e-postasını maskeleme (örn: ah***@domain.com)
    email = user.email
    masked_email = ""
    if email and "@" in email:
        parts = email.split("@", 1)
        local = parts[0]
        domain = parts[1]
        masked_email = (local[:2] + "***@" + domain) if len(local) > 2 else (local + "***@" + domain)

    return render(request, 'tickets/verify_2fa.html', {
        'username': user.username,
        'masked_email': masked_email,
    })


# ==========================================
# HAZIR YANIT ŞABLONLARI (CANNED RESPONSES) API
# ==========================================

@login_required
def canned_responses_api(request):
    """
    Destek ekibi için kategoriye göre filtrelenmiş hazır yanıt şablonlarını JSON olarak döndürür.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Yetkisiz işlem'}, status=403)

    category_id = request.GET.get('category_id')
    qs = CannedResponse.objects.all()
    if category_id:
        qs = qs.filter(Q(category_id=category_id) | Q(category__isnull=True))

    data = [
        {
            'id': cr.id,
            'title': cr.title,
            'content': cr.content,
            'category': cr.category.name if cr.category else None,
        }
        for cr in qs
    ]
    return JsonResponse({'status': 'success', 'canned_responses': data})


# ==========================================
# E-POSTA ÜZERİNDEN YANITLAMA (INBOUND EMAIL WEBHOOK)
# ==========================================

@csrf_exempt
@require_POST
def inbound_email_webhook(request):
    """
    Gelen e-postaları ayrıştırarak doğrudan ilgili destek talebine yorum olarak ekleyen webhook.
    E-posta başlığından / konusundan (#DES-XXXXX veya #ID) talep bulunur.
    Güvenlik: 'X-Webhook-Secret' başlığı veya ?token= parametresi ile doğrulanır.
    """
    import hmac
    from django.conf import settings
    expected_secret = getattr(settings, 'INBOUND_EMAIL_WEBHOOK_SECRET', settings.SECRET_KEY[:32])

    provided_secret = request.headers.get('X-Webhook-Secret') or request.GET.get('token')
    if not provided_secret or not hmac.compare_digest(str(provided_secret), str(expected_secret)):
        return JsonResponse({'error': 'Geçersiz webhook gizli anahtarı (secret).'}, status=403)

    try:
        # JSON veya Standart Form/Multipart veri desteği
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = request.POST.dict()

        sender_raw = payload.get('from') or payload.get('sender') or ''
        subject = payload.get('subject') or ''
        body = payload.get('text') or payload.get('body') or payload.get('html') or ''

        # 1. Talep Numarasını Tespit Et (#DES-XXXXX veya #ID)
        ticket_match = re.search(r'#(?:DES-)?([A-Za-z0-9-]+)', subject)
        if not ticket_match:
            ticket_match = re.search(r'#(?:DES-)?([A-Za-z0-9-]+)', body)

        if not ticket_match:
            return JsonResponse({'error': 'E-posta başlığında veya içeriğinde geçerli talep takip numarası (#DES-...) bulunamadı.'}, status=400)

        raw_num = ticket_match.group(1).strip()
        clean_digits = re.sub(r'\D', '', raw_num)
        ticket = None
        if clean_digits and clean_digits.isdigit():
            ticket = Ticket.objects.filter(id=int(clean_digits)).first()
        if not ticket and raw_num.isdigit():
            ticket = Ticket.objects.filter(id=int(raw_num)).first()

        if not ticket:
            return JsonResponse({'error': f"'{raw_num}' numaralı talep bulunamadı."}, status=404)

        # 2. Gönderici Kullanıcıyı Tespit Et
        email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender_raw)
        sender_email = email_match.group(0).lower() if email_match else ''
        author = User.objects.filter(email__iexact=sender_email).first()

        if not author:
            # Sistemde kayıtlı değilse talep sahibini varsay
            author = ticket.created_by

        # 3. Alıntı / Geçmiş Metinleri Temizle
        cleaned_lines = []
        for line in body.splitlines():
            stripped = line.strip()
            # Standart mail alıntı satırlarını atla
            if stripped.startswith('>') or stripped.startswith('---') or (stripped.startswith('On ') and 'wrote:' in stripped):
                break
            if 'Kimden:' in stripped and 'Tarih:' in stripped:
                break
            cleaned_lines.append(line)

        clean_text = "\n".join(cleaned_lines).strip()
        if not clean_text:
            clean_text = body.strip()

        # HTML / XSS Temizliği
        sanitized_content = nh3.clean(clean_text)

        # 4. Yorumu Kaydet
        comment = TicketComment.objects.create(
            ticket=ticket,
            author=author,
            content=sanitized_content,
            is_internal=False
        )

        # SLA İlk Yanıt Takibi
        if author.is_staff and not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
            ticket.save(update_fields=['first_response_at'])

        # 5. İlgili Taraflara Bildirim Gönder
        if author != ticket.created_by:
            Notification.objects.create(
                recipient=ticket.created_by,
                actor=author,
                ticket=ticket,
                message=f"#{ticket.ticket_number} talebinize e-posta yoluyla yeni yanıt eklendi."
            )

        if ticket.assigned_to and author != ticket.assigned_to:
            Notification.objects.create(
                recipient=ticket.assigned_to,
                actor=author,
                ticket=ticket,
                message=f"Sorumlu olduğunuz #{ticket.ticket_number} talebine e-posta üzerinden yanıt geldi."
            )

        # 6. Canlı WebSocket Grubuna Broadcast Gönder
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
                        "author_id": author.id,
                        "author_name": author.get_full_name() or author.username,
                        "is_staff": author.is_staff,
                        "is_internal": False,
                        "content": comment.content,
                        "attachment_url": "",
                        "attachment_name": "",
                        "created_at": comment.created_at.strftime("%d.%m.%Y %H:%M")
                    }
                )
        except Exception:
            pass

        return JsonResponse({
            'status': 'success',
            'ticket_id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'comment_id': comment.id,
            'message': 'E-posta yanıtı başarıyla talebe eklendi ve canlı yayınlandı.'
        })

    except Exception as e:
        return JsonResponse({'error': f'Ayrıştırma hatası: {str(e)}'}, status=500)


# ==========================================
# RESMİ TALEP RAPORU (PDF DIŞA AKTARMA)
# ==========================================

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


# ==========================================
# YAPAY ZEKÂ TALEP ASİSTANI (AI COPILOT) API
# ==========================================

@login_required
def ai_suggest_meta_api(request):
    """
    Talep formu doldurulurken girilen başlık ve açıklamayı analiz ederek
    otomatik kategori ve öncelik önerileri sunan canlı API.
    """
    title = request.GET.get('title') or request.POST.get('title') or ''
    description = request.GET.get('description') or request.POST.get('description') or ''

    if len(title.strip()) < 3 and len(description.strip()) < 5:
        return JsonResponse({'status': 'idle', 'message': 'Yeterli metin girilmedi.'})

    categories = Category.objects.all()
    suggestion = suggest_category_and_priority(title, description, categories)
    return JsonResponse({
        'status': 'success',
        **suggestion
    })


@login_required
def ai_summarize_ticket_api(request, pk):
    """
    Destek personeli için talep ve çözüm sürecini 1 cümlelik özet halinde sunan API.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim.'}, status=403)

    ticket = get_object_or_404(Ticket.objects.select_related('created_by', 'category'), pk=pk)
    summary = generate_ticket_summary(ticket)
    return JsonResponse({
        'status': 'success',
        'ticket_id': ticket.id,
        'ticket_number': ticket.ticket_number,
        'summary': summary
    })


