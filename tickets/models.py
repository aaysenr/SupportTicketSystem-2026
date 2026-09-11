import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .validators import validate_file_security


class EmailVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    def generate_code(self):
        """Kriptografik olarak güvenli 6 haneli rastgele kod üretir"""
        self.code = ''.join(secrets.choice('0123456789') for _ in range(6))
        self.created_at = timezone.now()
        self.failed_attempts = 0
        self.save()

    def is_valid(self):
        """Kodun 10 dakika boyunca geçerli ve en fazla 5 hatalı deneme ile sınırlı olmasını sağlar"""
        if self.failed_attempts >= 5:
            return False
        now = timezone.now()
        diff = now - self.created_at
        return diff.total_seconds() < 600  # 600 saniye = 10 dakika


class Category(models.Model):
    """Destek talepleri ve makaleler için departman/kategori modeli."""
    name = models.CharField(max_length=100, verbose_name="Kategori Adı")
    description = models.TextField(blank=True, null=True, verbose_name="Açıklama")

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategoriler"

    def __str__(self):
        return self.name


def is_holiday_or_weekend(dt):
    """
    Tarihin hafta sonu (Cumartesi, Pazar) veya resmi/dini bayram tatili
    olup olmadığını kontrol eder.
    """
    # 1. Hafta sonu mu? (Cumartesi: 5, Pazar: 6)
    if dt.weekday() in (5, 6):
        return True

    # 2. Türkiye Sabit Resmi Tatilleri (Ay, Gün)
    fixed_holidays = {
        (1, 1),    # Yılbaşı
        (4, 23),   # Ulusal Egemenlik ve Çocuk Bayramı
        (5, 1),    # Emek ve Dayanışma Günü
        (5, 19),   # Atatürk'ü Anma, Gençlik ve Spor Bayramı
        (7, 15),   # 15 Temmuz Demokrasi ve Milli Birlik Günü
        (8, 30),   # Zafer Bayramı
        (10, 29),  # Cumhuriyet Bayramı
    }
    if (dt.month, dt.day) in fixed_holidays:
        return True

    # 3. Dini Bayram Tatil Takvimi (2025 - 2028 Ramazan & Kurban Bayramları)
    religious_holidays = {
        # 2025
        (2025, 3, 30), (2025, 3, 31), (2025, 4, 1),
        (2025, 6, 6), (2025, 6, 7), (2025, 6, 8), (2025, 6, 9),
        # 2026
        (2026, 3, 20), (2026, 3, 21), (2026, 3, 22),
        (2026, 5, 27), (2026, 5, 28), (2026, 5, 29), (2026, 5, 30),
        # 2027
        (2027, 3, 10), (2027, 3, 11), (2027, 3, 12),
        (2027, 5, 17), (2027, 5, 18), (2027, 5, 19), (2027, 5, 20),
        # 2028
        (2028, 2, 27), (2028, 2, 28), (2028, 2, 29),
        (2028, 5, 5), (2028, 5, 6), (2028, 5, 7), (2028, 5, 8),
    }
    if (dt.year, dt.month, dt.day) in religious_holidays:
        return True

    return False


def add_business_hours(start_dt, hours):
    """
    Hafta içi 09:00 - 18:00 mesai saatlerine göre hedef teslim tarihini hesaplar.
    Hafta sonlarını (Cumartesi, Pazar) ve Türkiye resmi/dini tatil günlerini atlar.
    """
    from datetime import time, timedelta
    from django.utils import timezone

    if not start_dt:
        return None

    tz = timezone.get_current_timezone()
    current = start_dt.astimezone(tz) if timezone.is_aware(start_dt) else timezone.make_aware(start_dt, tz)

    WORK_START = time(9, 0)
    WORK_END = time(18, 0)

    # 1. Başlangıç anı tatil gününe denk geliyorsa ilk çalışma günü 09:00'a taşı
    while is_holiday_or_weekend(current):
        current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    # 2. Çalışma günü mesai öncesi ise 09:00'a taşı
    if current.time() < WORK_START:
        current = current.replace(hour=9, minute=0, second=0, microsecond=0)
    # Çalışma günü mesai sonrası ise ertesi iş günü 09:00'a taşı
    elif current.time() >= WORK_END:
        current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        while is_holiday_or_weekend(current):
            current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    remaining_minutes = int(hours * 60)

    while remaining_minutes > 0:
        day_end = current.replace(hour=18, minute=0, second=0, microsecond=0)
        minutes_left_today = int((day_end - current).total_seconds() // 60)

        if remaining_minutes <= minutes_left_today:
            current = current + timedelta(minutes=remaining_minutes)
            remaining_minutes = 0
        else:
            remaining_minutes -= minutes_left_today
            current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            while is_holiday_or_weekend(current):
                current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    return current


class Ticket(models.Model):
    """Destek talepleri modeli."""

    STATUS_CHOICES = (
        ('open', 'Açık'),
        ('in_progress', 'Devam Ediyor'),
        ('resolved', 'Çözüldü'),
        ('closed', 'Kapalı'),
    )

    PRIORITY_CHOICES = (
        ('low', 'Düşük'),
        ('medium', 'Orta'),
        ('high', 'Yüksek'),
        ('urgent', 'Acil'),
    )

    title = models.CharField(max_length=200, verbose_name="Başlık")
    description = models.TextField(verbose_name="Açıklama")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name="Kategori"
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        db_index=True,
        verbose_name="Öncelik"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        db_index=True,
        verbose_name="Durum"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='tickets',
        verbose_name="Oluşturan Kullanıcı"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        verbose_name="Atanan Yönetici"
    )
    attachment = models.FileField(
        upload_to='ticket_attachments/%Y/%m/%d/',
        blank=True,
        null=True,
        validators=[validate_file_security],
        verbose_name="Dosya / Görsel Eki"
    )
    is_public = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Herkese Açık (Topluluk / Forum Talebi)",
        help_text="İşaretlenirse tüm kullanıcılar bu talebi ve çözümünü görebilir. İşaretlenmezse sadece yöneticiler görebilir."
    )
    first_response_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="İlk Yanıt Tarihi",
        help_text="Destek yetkilisi tarafından ilk yanıtın verildiği zaman."
    )
    sla_deadline = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="SLA Son Tarihi",
        help_text="SLA hedef teslim / ilk yanıt tarihi."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")

    class Meta:
        verbose_name = "Destek Talebi"
        verbose_name_plural = "Destek Talepleri"
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.id} - {self.title}"
        #Talep nesnesi gösterilirken " #1 - Ekran Kırıldı"  şeklinde ID ve başlık kombinasyonu döndürür.

    def save(self, *args, **kwargs):
        # SLA hedef süresini oluşturulma anında veya öncelik/tarih değişiminde bir kez hesapla
        base_time = self.created_at or timezone.now()
        if not self.sla_deadline:
            self.sla_deadline = add_business_hours(base_time, self.sla_target_hours)
        elif self.created_at:
            expected_deadline = add_business_hours(self.created_at, self.sla_target_hours)
            if self.sla_deadline != expected_deadline:
                self.sla_deadline = expected_deadline
        super().save(*args, **kwargs)

    @property
    def ticket_number(self):
        # ID'yi 5 haneli yapıp başına DES- koyar (Örn: DES-00005)
        return f"DES-{self.id:05d}"

    @property
    def attachment_filename(self):
        if self.attachment and self.attachment.name:
            import os
            return os.path.basename(self.attachment.name)
        return ""

    @property
    def sla_target_hours(self):
        """Önceliğe göre hedeflenen ilk yanıt süresi (saat)."""
        targets = {
            'urgent': 2,
            'high': 6,
            'medium': 24,
            'low': 48,
        }
        return targets.get(self.priority, 24)

    @property
    def is_sla_breached(self):
        """İlk yanıt süresi SLA hedefinin aşıldığını belirler."""
        if not self.sla_deadline:
            return False
        if self.first_response_at:
            return self.first_response_at > self.sla_deadline
        if self.status in ['resolved', 'closed']:
            return False
        return timezone.now() > self.sla_deadline

    @property
    def sla_remaining_text(self):
        """SLA için kalan veya geciken süreyi kullanıcı dostu metin olarak döndürür."""
        if self.first_response_at:
            diff = self.first_response_at - self.created_at
            total_minutes = int(diff.total_seconds() // 60)
            hours = total_minutes // 60
            mins = total_minutes % 60
            if hours > 0:
                return f"{hours} sa {mins} dk içinde yanıtlandı"
            return f"{mins} dk içinde yanıtlandı"
        
        deadline = self.sla_deadline
        if not deadline:
            return ""
        now = timezone.now()
        if now > deadline:
            overdue = now - deadline
            total_minutes = int(overdue.total_seconds() // 60)
            hours = total_minutes // 60
            mins = total_minutes % 60
            if hours > 0:
                return f"{hours} sa {mins} dk gecikti"
            return f"{mins} dk gecikti"
        else:
            remaining = deadline - now
            total_minutes = int(remaining.total_seconds() // 60)
            hours = total_minutes // 60
            mins = total_minutes % 60
            if hours > 0:
                return f"{hours} sa {mins} dk kaldı"
            return f"{mins} dk kaldı"


class TicketComment(models.Model):
    """Destek talepleri altındaki yanıt ve yorumlar modeli."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments', verbose_name="Destek Talebi")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Yazan Kullanıcı")
    content = models.TextField(verbose_name="Yorum / Cevap")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Tarih")
    is_internal = models.BooleanField(default=False, verbose_name="İç Not (Sadece Yöneticiler Görsün)")
    attachment = models.FileField(
        upload_to='comment_attachments/%Y/%m/%d/',
        blank=True,
        null=True,
        validators=[validate_file_security],
        verbose_name="Dosya / Görsel Eki"
    )
    is_solution = models.BooleanField(default=False, db_index=True, verbose_name="En İyi Yanıt / Çözüm")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    likes = models.ManyToManyField(User, related_name='liked_comments', blank=True, verbose_name="Beğenen Kullanıcılar")

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def attachment_filename(self):
        if self.attachment and self.attachment.name:
            import os
            return os.path.basename(self.attachment.name)
        return ""

    class Meta:
        verbose_name = "Yorum"
        verbose_name_plural = "Yorumlar"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} - {self.ticket.title}"





class TicketActivityLog(models.Model):
    """
    Destek talebi üzerindeki tüm hareketlerin ve durum değişikliklerinin
    denetim (audit) geçmişini tutan model.
    """
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='activity_logs', verbose_name="Destek Talebi")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="İşlemi Yapan")
    action = models.CharField(max_length=255, verbose_name="Yapılan İşlem")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tarih")

    class Meta:
        verbose_name = "Talep Hareketi"
        verbose_name_plural = "Talep Hareketleri"
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.ticket.id} - {self.action} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"



class Notification(models.Model):
    """
    Kullanıcı içi canlı bildirimler modeli.
    """
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Bildirim Alıcısı")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Bildirimi Tetikleyen")
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, null=True, blank=True, verbose_name="İlişkili Talep")
    message = models.CharField(max_length=255, verbose_name="Bildirim Mesajı")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="Okundu Mu?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tarih")

    class Meta:
        verbose_name = "Bildirim"
        verbose_name_plural = "Bildirimler"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.recipient.username} - {self.message}"




class ChatGroup(models.Model):
    """
    Yöneticiler için özel sohbet grupları ve Genel Ekip Odası modeli.
    """
    name = models.CharField(max_length=150, verbose_name="Grup Adı")
    is_general = models.BooleanField(default=False, verbose_name="Genel Ekip Odası Mı?")
    members = models.ManyToManyField(User, related_name='chat_groups', verbose_name="Grup Üyeleri")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Oluşturan Yönetici")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")

    class Meta:
        verbose_name = "Sohbet Grubu"
        verbose_name_plural = "Sohbet Grupları"

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    """
    Yöneticiler arası Grup sohbeti ve Birebir (DM) mesajlaşma modeli.
    """
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_chat_messages', verbose_name="Gönderen")
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, null=True, blank=True, related_name='messages', verbose_name="İlişkili Grup")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='received_chat_messages', verbose_name="Alıcı (Özel Mesaj)")
    content = models.TextField(verbose_name="Mesaj İçeriği")
    is_read = models.BooleanField(default=False, verbose_name="Okundu mu?")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Tarih")

    class Meta:
        verbose_name = "Sohbet Mesajı"
        verbose_name_plural = "Sohbet Mesajları"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['sender', 'recipient', 'created_at']),
            models.Index(fields=['group', 'created_at']),
        ]

    def __str__(self):
        return f"{self.sender.username}: {self.content[:30]}"


class UserProfile(models.Model):
    """
    Gelişmiş Yönetici Rolleri (RBAC) ve Profil Modeli.
    Yöneticileri alt birimlere ayırır ve sorumlu oldukları kategorileri belirler.
    """
    ROLE_CHOICES = (
        ('superadmin', 'Süper Yönetici'),
        ('support_agent', 'Teknik Destek Uzmanı'),
        ('finance_agent', 'Finans Destek Uzmanı'),
        ('user', 'Standart Kullanıcı'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="Kullanıcı")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='user', verbose_name="Kullanıcı Rolü")
    assigned_categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name='assigned_staff',
        verbose_name="Sorumlu Olduğu Kategoriler",
        help_text="Teknik Destek veya Finans yetkilileri için sorumlu oldukları departman/kategorileri seçiniz."
    )
    is_2fa_enabled = models.BooleanField(default=False, verbose_name="2FA Aktif mi?")
    totp_secret = models.CharField(max_length=64, blank=True, null=True, verbose_name="2FA TOTP Gizli Anahtarı")
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Profil Fotoğrafı",
        validators=[validate_file_security]
    )

    class Meta:
        verbose_name = "Kullanıcı Profili ve Rolü"
        verbose_name_plural = "Kullanıcı Profilleri ve Rolleri"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Yetkili rolü seçildiğinde kullanıcının is_staff durumunu güvenli güncelle (signal tetiklemeden)
        if self.role in ['superadmin', 'support_agent', 'finance_agent']:
            if self.user_id and not self.user.is_staff:
                User.objects.filter(id=self.user_id).update(is_staff=True)
                self.user.is_staff = True
        elif self.role == 'user' and self.user_id and not self.user.is_superuser:
            if self.user.is_staff:
                User.objects.filter(id=self.user_id).update(is_staff=False)
                self.user.is_staff = False

    @property
    def is_superadmin(self):
        return self.role == 'superadmin' or self.user.is_superuser

    @property
    def is_staff_agent(self):
        return self.is_superadmin or self.role in ['support_agent', 'finance_agent'] or self.user.is_staff

    @property
    def avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return None

    def can_access_category(self, category):
        """Bu yetkilinin ilgili kategoriye erişim izni olup olmadığını denetler."""
        if self.is_superadmin:
            return True
        if not category:
            return True
        return self.assigned_categories.filter(id=category.id).exists()


from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Her kullanıcı oluşturulduğunda veya güncellendiğinde UserProfile nesnesini senkronize eder."""
    profile, _ = UserProfile.objects.get_or_create(user=instance)
    if instance.is_superuser and profile.role != 'superadmin':
        profile.role = 'superadmin'
        profile.save()
    elif instance.is_staff and profile.role == 'user':
        profile.role = 'support_agent'
        profile.save()


@receiver(post_delete, sender=Ticket)
def delete_ticket_attachment_on_delete(sender, instance, **kwargs):
    """Talep silindiğinde sunucuda kalan fiziksel ek dosyasını diskten temizler (Disk şişmesini engeller)"""
    if instance.attachment and instance.attachment.name:
        instance.attachment.delete(save=False)


@receiver(post_delete, sender=TicketComment)
def delete_comment_attachment_on_delete(sender, instance, **kwargs):
    """Yorum silindiğinde sunucuda kalan fiziksel ek dosyasını diskten temizler"""
    if instance.attachment and instance.attachment.name:
        instance.attachment.delete(save=False)


@receiver(post_delete, sender=UserProfile)
def delete_avatar_on_delete(sender, instance, **kwargs):
    """Kullanıcı profili silindiğinde fiziksel avatar dosyasını diskten temizler"""
    if instance.avatar and instance.avatar.name:
        instance.avatar.delete(save=False)



class KnowledgeBaseArticle(models.Model):
    """Sıkça sorulan sorular (SSS) ve bilgi bankası makalelerini tutan model."""
    CATEGORY_CHOICES = (
        ('general', 'Genel Bilgiler'),
        ('account', 'Hesap & Güvenlik'),
        ('billing', 'Faturalandırma & Ödeme'),
        ('technical', 'Teknik Sorunlar & Hatalar'),
    )

    title = models.CharField(max_length=200, verbose_name="Makale Başlığı")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kb_articles',
        verbose_name="Kategori"
    )
    content = models.TextField(verbose_name="Makale İçeriği")
    keywords = models.CharField(max_length=255, blank=True, verbose_name="Anahtar Kelimeler", help_text="Arama eşleştirmesi için anahtar kelimeler (virgülle ayırın)")
    views_count = models.PositiveIntegerField(default=0, verbose_name="Görüntülenme Sayısı")
    is_published = models.BooleanField(default=True, verbose_name="Yayında mı?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")

    class Meta:
        verbose_name = "Bilgi Bankası Makalesi"
        verbose_name_plural = "Bilgi Bankası Makaleleri"
        ordering = ['-views_count', '-created_at']

    def __str__(self):
        return self.title


class TicketRating(models.Model):
    """Çözülen talepler için müşteri memnuniyet (CSAT) değerlendirmesi."""
    SCORE_CHOICES = (
        (5, '⭐⭐⭐⭐⭐ - Çok Memnun Kaldım (5/5)'),
        (4, '⭐⭐⭐⭐ - Memnun Kaldım (4/5)'),
        (3, '⭐⭐⭐ - Orta (3/5)'),
        (2, '⭐⭐ - Memnun Kalmadım (2/5)'),
        (1, '⭐ - Hiç Memnun Kalmadım (1/5)'),
    )

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='rating', verbose_name="Destek Talebi")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Değerlendiren Kullanıcı")
    score = models.PositiveSmallIntegerField(choices=SCORE_CHOICES, verbose_name="Memnuniyet Puanı")
    feedback = models.TextField(blank=True, null=True, verbose_name="Görüş ve Öneriler")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Değerlendirme Tarihi")

    class Meta:
        verbose_name = "Talep Memnuniyet Değerlendirmesi"
        verbose_name_plural = "Talep Memnuniyet Değerlendirmeleri"
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.ticket.id} Değerlendirmesi: {self.score}/5"


class CannedResponse(models.Model):
    """Destek ekibinin sık kullandığı hazır yanıt şablonları."""
    title = models.CharField(max_length=150, verbose_name="Şablon Başlığı")
    content = models.TextField(verbose_name="Yanıt Metni")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='canned_responses',
        verbose_name="Kategori",
        help_text="Belirli bir kategoriye özel şablon için seçin veya tüm taleplerde geçerli olması için boş bırakın."
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='canned_responses',
        verbose_name="Oluşturan"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")

    class Meta:
        verbose_name = "Hazır Yanıt Şablonu"
        verbose_name_plural = "Hazır Yanıt Şablonları"
        ordering = ['title']

    def __str__(self):
        return self.title
