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




@login_required
@require_POST
def create_tag_api(request):
    """
    Kullanıcı arayüzünden hızlıca yeni etiket tanımlama API'si.
    Tüm giriş yapmış kullanıcılar yeni etiket oluşturabilir.
    """
    
    import json
    from django.utils.text import slugify

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    name = data.get('name', '').strip()[:20]
    color = '#3B82F6'  # Etiket rengi daima standart mavi

    if not name:
        return JsonResponse({'status': 'error', 'message': 'Etiket adı boş bırakılamaz.'}, status=400)

    # Aynı isimde varsa mevcut olanı döndür
    existing = TicketTag.objects.filter(name__iexact=name).first()
    if existing:
        return JsonResponse({
            'status': 'success',
            'tag': {
                'id': existing.id,
                'name': existing.name,
                'color': '#3B82F6',
                'slug': existing.slug
            }
        })

    base_slug = slugify(name) or 'etiket'
    slug = base_slug
    counter = 1
    while TicketTag.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    tag = TicketTag.objects.create(name=name, slug=slug, color='#3B82F6')
    return JsonResponse({
        'status': 'success',
        'tag': {
            'id': tag.id,
            'name': tag.name,
            'color': tag.color,
            'slug': tag.slug
        }
    })




@login_required
def list_tags_api(request):
    """
    Tüm etiketleri JSON olarak listeler (Yöneticiler için düzenleme modalı).
    """
    tags = TicketTag.objects.all().order_by('name')
    data = [{
        'id': t.id,
        'name': t.name,
        'slug': t.slug,
        'ticket_count': t.tickets.count()
    } for t in tags]
    return JsonResponse({'status': 'success', 'tags': data})




@login_required
@require_POST
def edit_tag_api(request, pk):
    """
    Yöneticilerin mevcut bir etiketi yeniden adlandırmasını sağlar.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Etiket düzenleme yetkiniz yok.'}, status=403)

    tag = get_object_or_404(TicketTag, pk=pk)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    new_name = data.get('name', '').strip()[:20]
    if not new_name:
        return JsonResponse({'status': 'error', 'message': 'Etiket adı boş bırakılamaz.'}, status=400)

    # Başka bir etiket bu ada sahip mi?
    conflict = TicketTag.objects.filter(name__iexact=new_name).exclude(pk=tag.pk).first()
    if conflict:
        return JsonResponse({'status': 'error', 'message': 'Bu isimde bir etiket zaten mevcut.'}, status=400)

    from django.utils.text import slugify
    tag.name = new_name
    base_slug = slugify(new_name) or 'etiket'
    slug = base_slug
    counter = 1
    while TicketTag.objects.filter(slug=slug).exclude(pk=tag.pk).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    tag.slug = slug
    tag.save(update_fields=['name', 'slug'])

    return JsonResponse({
        'status': 'success',
        'tag': {
            'id': tag.id,
            'name': tag.name,
            'slug': tag.slug
        }
    })




@login_required
@require_POST
def delete_tag_api(request, pk):
    """
    Yöneticilerin var olan bir etiketi silmesini sağlar.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Etiket silme yetkiniz yok.'}, status=403)

    tag = get_object_or_404(TicketTag, pk=pk)
    tag_id = tag.id
    tag.delete()

    return JsonResponse({'status': 'success', 'deleted_id': tag_id})


# --- ÖZEL HATA SAYFALARI (404, 403, 500) GÖRÜNÜMLERİ ---


