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
def delete_notification(request, pk):
    """
    Kullanıcının seçili bildirimini siler.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'status': 'success', 'message': 'Bildirim silindi.'})
    messages.success(request, "Bildirim silindi.")
    return redirect('notifications_list')




@login_required
def delete_all_notifications(request):
    """
    Kullanıcının tüm bildirimlerini siler.
    """
    count, _ = Notification.objects.filter(recipient=request.user).delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'status': 'success', 'deleted_count': count})
    messages.success(request, f"Tüm bildirimleriniz ({count} adet) silindi.")
    return redirect('notifications_list')

   


