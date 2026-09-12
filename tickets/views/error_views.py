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


def custom_404_view(request, exception=None):
    """Özel 404 Sayfa Bulunamadı hata ekranı."""
    return render(request, '404.html', status=404)




def custom_403_view(request, exception=None):
    """Özel 403 Erişim Yetkisi Yok hata ekranı."""
    return render(request, '403.html', status=403)




def custom_500_view(request):
    """Özel 500 Sunucu Hatası ekranı."""
    return render(request, '500.html', status=500)




