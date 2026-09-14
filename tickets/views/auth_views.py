from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.core.mail import send_mail
from django.core.cache import cache
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from ..models import Ticket, EmailVerification, TicketActivityLog, UserProfile
from ..forms import UserRegisterForm, UserProfileForm
from ..totp import (
    generate_totp_secret, verify_totp_token,
    get_totp_uri, generate_qr_code_data_uri
)


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

        # Form doğrulamasını tetikle (clean_email ve captcha kontrolü çalışsın)
        _ = form.errors

        # Onay bekleyen (is_active=False) mevcut bir hesap varsa ve güvenlik kodu doğruysa:
        if getattr(form, 'inactive_user', None) and 'captcha' not in form.errors:
            user = form.inactive_user
            verification, _ = EmailVerification.objects.get_or_create(user=user)
            verification.generate_code()

            try:
                send_mail(
                    subject="E-Posta Dogrulama Kodu",
                    message=f"Merhaba {user.username},\n\nHesabınız zaten mevcut ancak henüz onaylanmamış. Yeni doğrulama kodunuz: {verification.code}\n\nBu kod 10 dakika süreyle geçerlidir.",
                    from_email=None,
                    recipient_list=[user.email],
                    fail_silently=True
                )
            except Exception:
                pass

            request.session['unverified_user_id'] = user.id
            messages.info(request, "Hesabınız zaten mevcut ancak onaylanmamış. Yeni onay kodu gönderildi.")
            return redirect('verify_email')

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





def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip or '127.0.0.1'


def login_user(request):
    """
    Kullanıcı giriş görünümü. ?next= yönlendirmesini destekler ve onaylanmamış hesapları doğrulama sayfasına aktarır.
    Brute-force kaba kuvvet saldırılarına karşı IP bazlı hız sınırlaması ve geçici kilitleme içerir.
    """
    if request.user.is_authenticated:
        return redirect('ticket_list')

    client_ip = _get_client_ip(request)
    lockout_key = f"login_lockout_{client_ip}"
    attempts_key = f"login_attempts_{client_ip}"

    if cache.get(lockout_key):
        messages.error(
            request,
            "Çok fazla başarısız giriş denemesi yaptınız. Güvenliğiniz için erişiminiz 10 dakika süreyle kilitlenmiştir. Lütfen daha sonra tekrar deneyiniz."
        )
        return render(request, 'tickets/login.html', {
            'form': AuthenticationForm(),
            'next': request.GET.get('next', '')
        })

    if request.method == 'POST':
        post_data = request.POST.copy()
        raw_username = post_data.get('username', '').strip()

        # Kullanıcı kullanıcı adı yerine e-posta ile giriş yapmak istemişse, username'i bul
        if '@' in raw_username:
            user_by_email = User.objects.filter(email__iexact=raw_username).first()
            if user_by_email:
                post_data['username'] = user_by_email.username

        form = AuthenticationForm(request, data=post_data)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                cache.delete(attempts_key)
                cache.delete(lockout_key)

                profile = getattr(user, 'profile', None)
                if profile and profile.is_2fa_enabled and profile.totp_secret:
                    request.session['2fa_user_id'] = user.id
                    request.session['2fa_next'] = request.POST.get('next') or request.GET.get('next') or ''
                    return redirect('verify_2fa')

                login(request, user)
                display_name = user.get_full_name() or user.username
                messages.success(request, f"Tekrar hoş geldiniz, {display_name}!")
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                return redirect('ticket_list')
            else:
                current_attempts = cache.get(attempts_key, 0) + 1
                cache.set(attempts_key, current_attempts, timeout=900)
                if current_attempts >= 5:
                    cache.set(lockout_key, True, timeout=600)
                    cache.delete(attempts_key)
                    messages.error(
                        request,
                        "Ardışık 5 kez hatalı giriş yapıldı. Güvenliğiniz nedeniyle erişiminiz 10 dakika süreyle kilitlenmiştir."
                    )
                else:
                    remaining = 5 - current_attempts
                    messages.error(request, f"Kullanıcı adı veya parola hatalı. Kalan deneme hakkı: {remaining}")
        else:
            username_input = request.POST.get('username', '').strip()
            password_input = request.POST.get('password', '')
            if username_input and password_input:
                unverified_user = User.objects.filter(
                    Q(username=username_input) | Q(email__iexact=username_input),
                    is_active=False
                ).first()
                if unverified_user and unverified_user.check_password(password_input):
                    request.session['unverified_user_id'] = unverified_user.id
                    messages.info(request, "Hesabınız henüz doğrulanmamış. Lütfen doğrulama kodunu giriniz.")
                    return redirect('verify_email')

            current_attempts = cache.get(attempts_key, 0) + 1
            cache.set(attempts_key, current_attempts, timeout=900)
            if current_attempts >= 5:
                cache.set(lockout_key, True, timeout=600)
                cache.delete(attempts_key)
                messages.error(
                    request,
                    "Ardışık 5 kez hatalı giriş yapıldı. Güvenliğiniz nedeniyle erişiminiz 10 dakika süreyle kilitlenmiştir."
                )
            else:
                remaining = 5 - current_attempts
                messages.error(request, f"Geçersiz giriş bilgileri. Kalan deneme hakkı: {remaining}")
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
            if user.email:
                try:
                    from .common import send_notification_email
                    send_notification_email(
                        subject="[Güvenlik Uyarısı] Hesap Şifreniz Değiştirildi",
                        message=(
                            f"Merhaba {user.username},\n\n"
                            f"Destek Talep Sistemi hesabınızın şifresi az önce başarıyla değiştirildi.\n\n"
                            f"Eğer bu işlemi siz gerçekleştirmediyseniz, lütfen vakit kaybetmeden sistem yöneticiniz ile iletişime geçiniz.\n\n"
                            f"İşlem Zamanı: {timezone.now().strftime('%d.%m.%Y %H:%M')}"
                        ),
                        recipient_list=[user.email]
                    )
                except Exception:
                    pass
            messages.success(request, "Şifreniz başarıyla değiştirildi!")
            return redirect('profile')
        else:
            messages.error(request, "Lütfen şifre değiştirme formundaki hataları düzeltin.")
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'tickets/change_password.html', {'form': form})





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
        if request.user.email:
            try:
                from .common import send_notification_email
                send_notification_email(
                    subject="[Güvenlik Uyarısı] İki Aşamalı Doğrulama (2FA) Devre Dışı Bırakıldı",
                    message=(
                        f"Merhaba {request.user.username},\n\n"
                        f"Destek Talep Sistemi hesabınızda İki Aşamalı Doğrulama (2FA) koruması devre dışı bırakılmıştır.\n\n"
                        f"Eğer bu işlemi siz gerçekleştirmediyseniz, hesabınız tehlikede olabilir. Lütfen derhal şifrenizi yenileyin ve sistem yöneticiniz ile iletişime geçiniz.\n\n"
                        f"İşlem Zamanı: {timezone.now().strftime('%d.%m.%Y %H:%M')}"
                    ),
                    recipient_list=[request.user.email]
                )
            except Exception:
                pass
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
            if '2fa_failed_attempts' in request.session:
                del request.session['2fa_failed_attempts']
            login(request, user)
            next_url = request.session.pop('2fa_next', None)
            if '2fa_user_id' in request.session:
                del request.session['2fa_user_id']
            messages.success(request, f"İki aşamalı doğrulama başarılı! Tekrar hoş geldiniz, {user.username}.")
            if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('ticket_list')
        else:
            failed_attempts = request.session.get('2fa_failed_attempts', 0) + 1
            request.session['2fa_failed_attempts'] = failed_attempts
            if failed_attempts >= 5:
                if '2fa_user_id' in request.session:
                    del request.session['2fa_user_id']
                if '2fa_next' in request.session:
                    del request.session['2fa_next']
                if '2fa_failed_attempts' in request.session:
                    del request.session['2fa_failed_attempts']
                messages.error(request, "5 ardışık hatalı 2FA kodu girildi. Güvenliğiniz için doğrulama oturumu sonlandırıldı. Lütfen baştan giriş yapınız.")
                return redirect('login')
            remaining = 5 - failed_attempts
            messages.error(request, f"Doğrulama kodu hatalı veya süresi geçmiş. Kalan deneme hakkı: {remaining}")

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
@require_POST
def delete_account_view(request):
    """
    Kullanıcı ve yönetici hesap silme işlemi.
    Klasik kurumsal veritabanı anlayışına (ITIL / KVKK) uygun olarak Soft-Delete ve Anonimleştirme uygular.
    Talepler, çözümler, yorumlar ve CSAT puanları veritabanı tutarlılığı için korunur.
    """
    password = request.POST.get('password', '').strip()
    if not request.user.check_password(password):
        messages.error(request, "Girdiğiniz mevcut hesap şifresi hatalı. Hesap silme işlemi iptal edildi.")
        return redirect('profile')

    user = request.user
    profile = getattr(user, 'profile', None)

    # Süper yönetici denetimi: Sistemde en az bir aktif süper yönetici kalmalıdır
    if user.is_superuser or (profile and profile.role == 'superadmin'):
        other_superadmins = User.objects.filter(is_active=True).filter(
            Q(is_superuser=True) | Q(profile__role='superadmin')
        ).exclude(id=user.id).count()
        if other_superadmins == 0:
            messages.error(
                request,
                "Sistemde en az bir aktif Süper Yönetici bulunmalıdır! Hesabınızı silmeden önce başka bir kullanıcıya Süper Yönetici yetkisi vermelisiniz."
            )
            return redirect('profile')

    with transaction.atomic():
        user_id = user.id
        old_username = user.username

        # 1. Açık veya işlemdeki atanmış talepleri ortak havuza aktar
        active_assigned_tickets = Ticket.objects.filter(
            assigned_to_id=user_id,
            status__in=['open', 'in_progress']
        )
        for t in active_assigned_tickets:
            t.assigned_to = None
            t.save(update_fields=['assigned_to', 'updated_at'])
            TicketActivityLog.objects.create(
                ticket=t,
                actor=None,
                action=f"Atanan yetkili ({old_username}) hesabı kapatıldığı için talep ortak yetkili havuzuna aktarıldı."
            )

        # 2. Varsa avatar dosyasını diskten temizle ve 2FA anahtarlarını sıfırla
        if profile:
            if profile.avatar and profile.avatar.name:
                profile.avatar.delete(save=False)
                profile.avatar = None
            profile.is_2fa_enabled = False
            profile.totp_secret = None
            profile.role = 'user'
            profile.assigned_categories.clear()
            profile.save()

        # 3. Kullanıcıyı pasifleştir ve kişisel verilerini anonimleştir (GDPR / KVKK)
        user.is_active = False
        user.is_staff = False
        user.is_superuser = False
        user.set_unusable_password()
        user.username = f"deleted_user_{user_id}"
        user.email = f"deleted_{user_id}@anonymized.local"
        user.first_name = "Silinmiş"
        user.last_name = "Kullanıcı"
        user.save()

        # 4. Oturumu sonlandır
        logout(request)
        messages.success(
            request,
            "Hesabınız başarıyla silindi ve kişisel verileriniz temizlendi. Destek sistemimizi kullandığınız için teşekkür ederiz."
        )
        return redirect('login')

