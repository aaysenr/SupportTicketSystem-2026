import json
import nh3

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone

from ..models import ChatGroup, ChatMessage, UserChatPreference
from ..consumers import ALLOWED_TAGS, ALLOWED_ATTRIBUTES


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

    # 3. Giriş yapan yöneticinin dahil olduğu Özel Gruplar ve Arşiv Durumu
    all_user_groups = ChatGroup.objects.filter(members=request.user, is_general=False)
    archived_group_ids = set(
        UserChatPreference.objects.filter(user=request.user, is_archived=True, group__isnull=False)
        .values_list('group_id', flat=True)
    )
    archived_dm_user_ids = set(
        UserChatPreference.objects.filter(user=request.user, is_archived=True, dm_user__isnull=False)
        .values_list('dm_user_id', flat=True)
    )

    user_groups = [g for g in all_user_groups if g.id not in archived_group_ids]
    archived_groups = [g for g in all_user_groups if g.id in archived_group_ids]

    for mgr in managers:
        mgr.is_dm_archived = mgr.id in archived_dm_user_ids

    # 4. Aktif Sohbet Kanalını Belirle
    active_channel = {
        'type': chat_type,
        'id': chat_id,
        'title': 'Genel Ekip Odası',
        'target_user': None,
        'group': general_group,
        'is_archived': False,
    }

    current_pref = None
    if chat_type == 'dm' and chat_id:
        recipient = get_object_or_404(User, id=chat_id, is_staff=True)
        active_channel['title'] = recipient.get_full_name() or recipient.username
        active_channel['target_user'] = recipient
        current_pref = UserChatPreference.objects.filter(user=request.user, dm_user=recipient).first()
        messages_list = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=recipient) |
            Q(sender=recipient, recipient=request.user)
        )
    elif chat_type == 'group' and chat_id:
        group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
        active_channel['title'] = group.name
        active_channel['group'] = group
        current_pref = UserChatPreference.objects.filter(user=request.user, group=group).first()
        messages_list = group.messages.all()
    else:
        active_channel['type'] = 'group'
        active_channel['id'] = general_group.id
        current_pref = UserChatPreference.objects.filter(user=request.user, group=general_group).first()
        messages_list = general_group.messages.all()

    if current_pref:
        active_channel['is_archived'] = current_pref.is_archived
        if current_pref.cleared_at:
            messages_list = messages_list.filter(created_at__gt=current_pref.cleared_at)

    messages_list = messages_list.filter(is_deleted=False).exclude(deleted_for_users=request.user).select_related('sender', 'sender__profile').prefetch_related('favorited_by').order_by('created_at')

    context = {
        'managers': managers,
        'general_group': general_group,
        'user_groups': user_groups,
        'archived_groups': archived_groups,
        'archived_dm_user_ids': archived_dm_user_ids,
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

        # XSS Temizliği
        clean_content = nh3.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
        if not clean_content:
            return JsonResponse({'status': 'error', 'message': 'Geçersiz mesaj içeriği'}, status=400)

        msg = None
        if chat_type == 'dm':
            recipient = get_object_or_404(User, id=chat_id, is_staff=True)
            msg = ChatMessage.objects.create(sender=request.user, recipient=recipient, content=clean_content)
        else:
            group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
            msg = ChatMessage.objects.create(sender=request.user, group=group, content=clean_content)

        now_local = timezone.localtime(msg.created_at)
        today = timezone.localdate()
        msg_date = now_local.date()
        if msg_date == today:
            date_display = "Bugün"
        elif msg_date == today - timezone.timedelta(days=1):
            date_display = "Dün"
        else:
            date_display = msg_date.strftime("%d.%m.%Y")

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
                        "created_at": now_local.strftime('%H:%M'),
                        "date_key": msg_date.strftime("%Y-%m-%d"),
                        "date_display": date_display,
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
            'created_at': now_local.strftime('%H:%M'),
            'date_key': msg_date.strftime("%Y-%m-%d"),
            'date_display': date_display,
        })

    return JsonResponse({'status': 'error', 'message': 'Geçersiz istek'}, status=400)




@login_required
@require_POST
def edit_chat_message_view(request, pk):
    """
    Kullanıcının kendi mesajını düzenlemesi.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim.'}, status=403)
    
    msg = get_object_or_404(ChatMessage, pk=pk)
    if msg.sender != request.user:
        return JsonResponse({'status': 'error', 'message': 'Yalnızca kendi mesajlarınızı düzenleyebilirsiniz.'}, status=403)
    
    body_data = {}
    if request.content_type == 'application/json':
        try:
            body_data = json.loads(request.body)
        except Exception:
            pass
    new_content = (body_data.get('content') or request.POST.get('content', '')).strip()
    if not new_content:
        return JsonResponse({'status': 'error', 'message': 'Mesaj boş olamaz.'}, status=400)
    
    clean_content = nh3.clean(new_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
    msg.content = clean_content
    msg.is_edited = True
    msg.save(update_fields=['content', 'is_edited'])
    now_local = timezone.localtime(msg.updated_at)
    updated_at_str = now_local.strftime("%H:%M")
    updated_at_full_str = now_local.strftime("%d.%m.%Y %H:%M")

    # Broadcast via channels
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            if msg.group:
                room_group = f"chat_group_{msg.group.id}"
            else:
                u1, u2 = sorted([msg.sender_id, msg.recipient_id])
                room_group = f"chat_dm_{u1}_{u2}"
            async_to_sync(channel_layer.group_send)(
                room_group,
                {
                    "type": "chat_message_edit_broadcast",
                    "message_id": msg.id,
                    "content": clean_content,
                    "updated_at": updated_at_str,
                    "updated_at_full": updated_at_full_str,
                }
            )
    except Exception:
        pass

    return JsonResponse({
        'status': 'success',
        'message_id': msg.id,
        'content': clean_content,
        'updated_at': updated_at_str,
        'updated_at_full': updated_at_full_str,
    })




@login_required
@require_POST
def delete_chat_message_view(request, pk):
    """
    Mesajı silme:
    - mode='for_me' (Benden Sil): Sadece işlemi yapan kullanıcının ekranından kaldırılır (kendi veya başkasının mesajı).
    - mode='for_everyone' (Herkesten Sil): Sadece mesajın sahibi veya süpervizör tarafından tüm sohbet için silinir.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim.'}, status=403)

    msg = get_object_or_404(ChatMessage, pk=pk)

    is_owner = (msg.sender == request.user or request.user.is_superuser)
    # Varsayılan mod: Eğer parametre verilmemişse ve kullanıcı mesaj sahibi ise 'for_everyone', başkası ise 'for_me'
    default_mode = 'for_everyone' if is_owner else 'for_me'

    mode = default_mode
    if request.content_type == 'application/json':
        try:
            body_data = json.loads(request.body)
            mode = body_data.get('mode', default_mode)
        except Exception:
            mode = default_mode
    else:
        mode = request.POST.get('mode', default_mode)

    # Başkasının mesajını sadece kendi sohbetinden silebilir ('for_me')
    if mode == 'for_everyone':
        if not is_owner:
            return JsonResponse({'status': 'error', 'message': 'Başkasının mesajını herkesten silemezsiniz, sadece kendinizden silebilirsiniz.'}, status=403)
        msg.is_deleted = True
        msg.save(update_fields=['is_deleted'])

        # Broadcast via channels to all members
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                if msg.group:
                    room_group = f"chat_group_{msg.group.id}"
                else:
                    u1, u2 = sorted([msg.sender_id, msg.recipient_id])
                    room_group = f"chat_dm_{u1}_{u2}"
                async_to_sync(channel_layer.group_send)(
                    room_group,
                    {
                        "type": "chat_message_delete_broadcast",
                        "message_id": msg.id
                    }
                )
        except Exception:
            pass

        return JsonResponse({'status': 'success', 'message_id': msg.id, 'mode': 'for_everyone'})

    else:
        # mode == 'for_me'
        msg.deleted_for_users.add(request.user)
        return JsonResponse({'status': 'success', 'message_id': msg.id, 'mode': 'for_me'})




@login_required
@require_POST
def toggle_favorite_chat_message_view(request, pk):
    """
    Mesajı favorilere ekler veya kaldırır.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim.'}, status=403)

    msg = get_object_or_404(ChatMessage, pk=pk)
    if msg.favorited_by.filter(id=request.user.id).exists():
        msg.favorited_by.remove(request.user)
        is_favorited = False
    else:
        msg.favorited_by.add(request.user)
        is_favorited = True

    return JsonResponse({'status': 'success', 'message_id': msg.id, 'is_favorited': is_favorited})




@login_required
@require_POST
def clear_chat_view(request):
    """
    Kullanıcının aktif sohbet (Grup veya DM) geçmişini kendi görünümünden temizler.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim.'}, status=403)

    body_data = {}
    if request.content_type == 'application/json':
        try:
            body_data = json.loads(request.body)
        except Exception:
            pass
    chat_type = body_data.get('chat_type') or request.POST.get('chat_type')
    chat_id = body_data.get('chat_id') or request.POST.get('chat_id')

    if not chat_type or not chat_id:
        return JsonResponse({'status': 'error', 'message': 'Eksik parametre.'}, status=400)

    if chat_type == 'dm':
        target_user = get_object_or_404(User, id=chat_id, is_staff=True)
        pref, _ = UserChatPreference.objects.get_or_create(user=request.user, dm_user=target_user)
    else:
        group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
        pref, _ = UserChatPreference.objects.get_or_create(user=request.user, group=group)

    pref.cleared_at = timezone.now()
    pref.save()

    return JsonResponse({'status': 'success', 'message': 'Sohbet geçmişi temizlendi.'})




@login_required
@require_POST
def toggle_archive_chat_view(request):
    """
    Aktif sohbeti arşivler veya arşivden çıkarır.
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim.'}, status=403)

    body_data = {}
    if request.content_type == 'application/json':
        try:
            body_data = json.loads(request.body)
        except Exception:
            pass
    chat_type = body_data.get('chat_type') or request.POST.get('chat_type')
    chat_id = body_data.get('chat_id') or request.POST.get('chat_id')

    if not chat_type or not chat_id:
        return JsonResponse({'status': 'error', 'message': 'Eksik parametre.'}, status=400)

    if chat_type == 'dm':
        target_user = get_object_or_404(User, id=chat_id, is_staff=True)
        pref, _ = UserChatPreference.objects.get_or_create(user=request.user, dm_user=target_user)
    else:
        group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
        pref, _ = UserChatPreference.objects.get_or_create(user=request.user, group=group)

    pref.is_archived = not pref.is_archived
    pref.save()

    return JsonResponse({'status': 'success', 'is_archived': pref.is_archived})




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

    pref = None
    if chat_type == 'dm':
        recipient = get_object_or_404(User, id=chat_id, is_staff=True)
        pref = UserChatPreference.objects.filter(user=request.user, dm_user=recipient).first()
        messages_qs = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=recipient) |
            Q(sender=recipient, recipient=request.user)
        )
    else:
        group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
        pref = UserChatPreference.objects.filter(user=request.user, group=group).first()
        messages_qs = group.messages.all()

    if pref and pref.cleared_at:
        messages_qs = messages_qs.filter(created_at__gt=pref.cleared_at)

    messages_qs = messages_qs.filter(is_deleted=False).exclude(deleted_for_users=request.user)

    if after_id and after_id.isdigit():
        messages_qs = messages_qs.filter(id__gt=int(after_id))

    messages_qs = messages_qs.order_by('created_at').prefetch_related('favorited_by')

    today = timezone.localdate()
    yesterday = today - timezone.timedelta(days=1)

    data = []
    for m in messages_qs:
        now_local = timezone.localtime(m.created_at)
        updated_local = timezone.localtime(m.updated_at) if m.updated_at else now_local
        m_date = now_local.date()
        if m_date == today:
            date_display = "Bugün"
        elif m_date == yesterday:
            date_display = "Dün"
        else:
            date_display = m_date.strftime("%d.%m.%Y")

        data.append({
            'message_id': m.id,
            'sender_id': m.sender.id,
            'sender_name': m.sender.get_full_name() or m.sender.username,
            'content': m.content,
            'created_at': now_local.strftime('%H:%M'),
            'updated_at': updated_local.strftime('%H:%M') if m.is_edited else '',
            'created_at_full': now_local.strftime('%d.%m.%Y %H:%M'),
            'updated_at_full': updated_local.strftime('%d.%m.%Y %H:%M') if m.is_edited else '',
            'date_key': m_date.strftime("%Y-%m-%d"),
            'date_display': date_display,
            'is_edited': m.is_edited,
            'is_starred': m.favorited_by.filter(id=request.user.id).exists(),
        })

    return JsonResponse({'messages': data})



