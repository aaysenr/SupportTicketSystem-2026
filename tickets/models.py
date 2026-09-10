import random
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .validators import validate_file_security


# İçe Aktarmalar (Imports)
# from django.db import models: Django'nun veritabanı yönetim araçlarını ve sütun tiplerini (CharField, ForeignKey vb.) projeye dahil eder.
# from django.contrib.auth.models import User: Django'nun hazır kullanıcı yönetimi modelini projeye aktarır.


class EmailVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    def generate_code(self):
        """6 haneli rastgele kod üretir"""
        self.code = str(random.randint(100000, 999999))
        self.created_at = timezone.now()
        self.save()
    def is_valid(self):
        """Kodun 10 dakika boyunca geçerli olmasını sağlar"""
        now = timezone.now()
        diff = now - self.created_at
        return diff.total_seconds() < 600 # 600 saniye = 10 dakika



class Category(models.Model):

    # Category adında bir model tanımlandı (veri tabanına Category isimli bir tablo oluştu)

    # Veritabanında bir kategori tablosu oluşturmak için Django'nun temel Model sınıfından türeyen bir sınıf tanımlar.

    name = models.CharField(max_length=100, verbose_name="Kategori Adı")

    # Maksimum 100 karakter uzunluğunda metin sütunu oluşturur. 
    # Formlarda ve adminde "Kategori Adı" olarak görünür.

    description = models.TextField(blank=True, null=True, verbose_name="Açıklama")
    
    # İsteğe bağlı açıklama alanı. 
    # blank=True: Formda boş bırakılabilir.
    # null=True: Veritabanında NULL olarak saklanabilir.
    # verbose_name: Admin arayüzünde görünecek başlık. "Açıklama" adıyla kullanıcıya gorunur.

    class Meta:
        # Meta sınıfı, bu modelin meta verilerini (ayarlarını) içerir.  (settings)
        # Modelin davranışını ve varsayılan ayarlarını yapılandıran alt sınıftır.
        verbose_name = "Kategori"
        # Bu modelin tekil isminin admin panelinde "Kategori" olarak gözükmesini sağlar.
        verbose_name_plural = "Kategoriler"
        # Bu modelin çoğul isminin admin panelinde "Kategoriler" olarak gözükmesini sağlar.

    def __str__(self):
        # Model nesnesinin metin temsilini döndürür.
        # Admin panelinde veya başka yerlerde modelin hangi nesne olduğunu gösterir.
        # Nesnenin ekranda metin olarak temsil edilmesini sağlayan varsayılan Python metodudur.
        return self.name
        # return self.name: Bu kategoriye ait hangi isim varsa onu döndürür.
        # Örneğin: "Teknik Destek" 
        #Kategori nesnesi çağrıldığında karmaşık bir kod yerine doğrudan kategori adını (ör. "Yazılım") döndürür.


def add_business_hours(start_dt, hours):
    """
    Hafta içi 09:00 - 18:00 mesai saatlerine göre hedef teslim tarihini hesaplar.
    Hafta sonlarını (Cumartesi, Pazar) ve mesai dışı saatleri atlar.
    """
    from datetime import time, timedelta
    from django.utils import timezone

    if not start_dt:
        return None

    tz = timezone.get_current_timezone()
    current = start_dt.astimezone(tz) if timezone.is_aware(start_dt) else timezone.make_aware(start_dt, tz)

    WORK_START = time(9, 0)
    WORK_END = time(18, 0)

    # 1. Başlangıç anı hafta sonu ise ilk Pazartesi 09:00'a taşı
    while current.weekday() in (5, 6):
        current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    # 2. Hafta içi mesai öncesi ise 09:00'a taşı
    if current.time() < WORK_START:
        current = current.replace(hour=9, minute=0, second=0, microsecond=0)
    # Hafta içi mesai sonrası ise ertesi iş günü 09:00'a taşı
    elif current.time() >= WORK_END:
        current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        while current.weekday() in (5, 6):
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
            while current.weekday() in (5, 6):
                current = (current + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    return current


class Ticket(models.Model):
    #Ticket adında bir model tanımlandı (veri tabanına Ticket isimli bir tablo oluştu)
    #Destek talepleri tablosunu tanımlar.

    # Öncelik Seçenekleri:

    #STATUS_CHOICES: Bir tuple listesidir. 
    # Tuple: Değiştirilemez veri yapısıdır.
  
    STATUS_CHOICES = (  # Talebin durum seçeneklerini tutan demet (tuple) yapısıdır.
        ('open', 'Açık'), # İlk eleman veritabanına kaydedilir ('open'), 
        ('in_progress', 'Devam Ediyor'), # ikinci eleman ekranda kullanıcıya gösterilir ('Devam Ediyor').  
        ('resolved', 'Çözüldü'), # üçüncü eleman ekranda kullanıcıya gösterilir ('Çözüldü'). 
        ('closed', 'Kapalı'), # dördüncü eleman ekranda kullanıcıya gösterilir ('Kapalı'). 
    )


    PRIORITY_CHOICES = (  # Talebin öncelik seçeneklerini tutan demet (tuple) yapısıdır.
        ('low', 'Düşük'), # İlk eleman veritabanına kaydedilir ('low'), 
        ('medium', 'Orta'), # ikinci eleman ekranda kullanıcıya gösterilir ('Orta').  
        ('high', 'Yüksek'), # üçüncü eleman ekranda kullanıcıya gösterilir ('Yüksek'). 
        ('urgent', 'Acil'), # dördüncü eleman ekranda kullanıcıya gösterilir ('Acil'). 
    )


    # Tablo Alanları
    
    title = models.CharField(max_length=200, verbose_name="Başlık") 
    # Maksimum 200 karakter uzunluğunda metin sütunu oluşturur.
    # Formlarda ve adminde "Başlık" olarak görünür.
    
    description = models.TextField(verbose_name="Açıklama")
    # İsteğe bağlı açıklama alanı.
    # Formlarda ve adminde "Açıklama" olarak görünür.

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', verbose_name="Kategori")
    # ForeignKey: İlişki kurar.
    # on_delete=models.SET_NULL: İlişki kurulduğunda kategori silinirse, ilişkili alan NULL olarak ayarlanır.
    # Kategori silindiğinde bu talebin silinmesini engeller, kategorisini boş (NULL) yapar.
    # null=True: İlişkili alan NULL olarak saklanabilir.
    # blank=True: İlişkili alan formda boş bırakılabilir.
    # related_name='tickets': İlişki kurulduğunda kategoriye ait talep listesini döndürür.
    #Bir kategori üzerinden o kategoriye ait tüm taleplere (category.tickets.all()) erişmeyi sağlar.
    # verbose_name: Formlarda ve adminde "Kategori" olarak görünür.

    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', db_index=True, verbose_name="Öncelik")
    #Öncelik seviyesi sütunudur. choices ile tanımlanan seçenekler dışına çıkılamaz, varsayılan değeri (default) 'medium' yani "Orta"dır.
    # max_length=20: Maksimum 20 karakter uzunluğunda metin sütunu oluşturur.
    # choices=PRIORITY_CHOICES: Seçenekler PRIORITY_CHOICES demetinden gelir.
    # default='medium': Varsayılan değer "medium" olarak ayarlanır.
    # verbose_name: Formlarda ve adminde "Öncelik" olarak görünür.

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', db_index=True, verbose_name="Durum")
    # Talebin durum sütunudur. Varsayılan değeri 'open' yani "Açık" olarak atanır.
    # max_length=20: Maksimum 20 karakter uzunluğunda metin sütunu oluşturur.
    # choices=STATUS_CHOICES: Seçenekler STATUS_CHOICES demetinden gelir.
    # default='open': Varsayılan değer "open" olarak ayarlanır.
    # verbose_name: Formlarda ve adminde "Durum" olarak görünür.
    
    # Kullanıcı İlişkisi
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets', verbose_name="Oluşturan Kullanıcı")
    # Talebi açan kullanıcıya bağlanan ilişkisel alandır. on_delete=models.CASCADE sayesinde kullanıcı silindiğinde ona ait talepler de veritabanından silinir.
    # Bir kullanıcının oluşturduğu tüm taleplere (user.tickets.all()) erişmeyi sağlar.
    # ForeignKey: İlişki kurar.
    # on_delete=models.CASCADE: İlişki kurulduğunda kullanıcı silinirse, ilişkili alan CASCADE ile silinir.
    # related_name='tickets': İlişki kurulduğunda kullanıcıya ait talep listesini döndürür.
    # verbose_name: Formlarda ve adminde "Oluşturan Kullanıcı" olarak görünür.
    

    # Talebe Atanan Yönetici (Boş bırakılabilir)
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,  # kullanıcı silinirse, ilişkili alan NULL olarak ayarlanır.
        null=True,  # veritabanında NULL olarak saklanabilir
        blank=True,  # boş bırakılabilir
        related_name='assigned_tickets',  # ilişki kurulduğunda kullanıcıya ait talep listesini döndürür.
        verbose_name="Atanan Yönetici"  # admin panelinde görünecek başlık
    )

    
    attachment = models.FileField(  # dosya ekleme
        upload_to='ticket_attachments/%Y/%m/%d/',  # dosya yükleme yolu
        blank=True,  # boş bırakılabilir
        null=True,  # veritabanında NULL olarak saklanabilir
        validators=[validate_file_security],
        verbose_name="Dosya / Görsel Eki" # admin panelinde görünecek başlık
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

    # Tarih Bilgileri
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    #Bu alan, talebin ilk kaydedildiği anı (saniye hassasiyetinde) otomatik olarak kaydeder.
    #Talebin ilk oluşturulduğu tarih ve saati otomatik kaydeder.


    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    #Bu alan, her kayıt işlemi (save) yapıldığında otomatik olarak güncellenir.
    #Talep üzerinde her güncelleme yapıldığında tarih/saat bilgisini o anın zamanıyla yeniler.

    class Meta:
        # Buradaki Meta Sınıfı : ticket'a ait genel ayarları tutar.
        verbose_name = "Destek Talebi"
        verbose_name_plural = "Destek Talepleri"
        ordering = ['-created_at'] # En yeni talepler en üstte görünsün
        #Talepleri veritabanından çekerken oluşturulma tarihine göre tersten (en yeni en üstte) sıralar.

    def __str__(self):
        return f"#{self.id} - {self.title}"
        #Talep nesnesi gösterilirken " #1 - Ekran Kırıldı"  şeklinde ID ve başlık kombinasyonu döndürür.

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
    def sla_deadline(self):
        """SLA son yanıt tarihi (Hafta içi 09:00 - 18:00 mesai saatlerine duyarlı)."""
        if self.created_at:
            return add_business_hours(self.created_at, self.sla_target_hours)
        return None

    @property
    def is_sla_breached(self):
        """İlk yanıt süresi SLA hedefinin aşıldığını belirler."""
        deadline = self.sla_deadline
        if not deadline:
            return False
        if self.first_response_at:
            return self.first_response_at > deadline
        if self.status in ['resolved', 'closed']:
            return False
        return timezone.now() > deadline

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
    #Taleplerin altına yazılan yorum ve cevapların tutulduğu tablo sınıfıdır.

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments', verbose_name="Destek Talebi")
    #  Yorumun hangi talebe ait olduğunu bağlar. 
    # Talep silinirse yorumları da silinir.
    #  related_name='comments' sayesinde bir talebin tüm yorumlarına (ticket.comments.all()) erişilebilir.
    # Yani her ticket'ın kendine ait comment listesi vardır


    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Yazan Kullanıcı")
    #Yorumu yazan kullanıcıyı tutar.    

    content = models.TextField(verbose_name="Yorum / Cevap")
    #Yorumun içeriğini tutar.

    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Tarih")
    #Yorumun oluşturulma tarihini tutar.

    is_internal = models.BooleanField(default=False, verbose_name="İç Not (Sadece Yöneticiler Görsün)")
    # Yöneticilere Özel İç Not: Bu alan işaretlendiğinde sadece yönetici kullanıcılar bu yorumu görebilir.
    # Kullanıcılar kendi taleplerine baktıklarında bu yorumu göremezler.
    # Varsayılan değeri False olduğu için, normal yorumlar tüm kullanıcılar tarafından görülür.
    # Eğer bir yönetici iç konuşma (örneğin teknik analiz, not alma) yapmak isterse bu alanı True yapabilir.

    attachment = models.FileField(  # dosya ekleme
        upload_to='comment_attachments/%Y/%m/%d/',  # dosya yükleme yolu
        blank=True,  # boş bırakılabilir
        null=True,  # veritabanında NULL olarak saklanabilir
        validators=[validate_file_security],
        verbose_name="Dosya / Görsel Eki"  # admin panelinde görünecek başlık
    )

    is_solution = models.BooleanField(default=False, db_index=True, verbose_name="En İyi Yanıt / Çözüm")
    # Bu yorumun talep sahibi veya yönetici tarafından "Çözüm" olarak seçilip seçilmediğini tutar.

    likes = models.ManyToManyField(User, related_name='liked_comments', blank=True, verbose_name="Beğenen Kullanıcılar")
    # Yorumu faydalı bulup beğenen kullanıcıların listesi.

    @property
    def like_count(self):
        # Yorumun kaç kişi tarafından beğenildiğini sayar.
        return self.likes.count()

    @property
    def attachment_filename(self):
        if self.attachment and self.attachment.name:
            import os
            return os.path.basename(self.attachment.name)
        return ""

    class Meta:
        #Yorumlara ait genel ayarlar
        verbose_name = "Yorum"
        verbose_name_plural = "Yorumlar"
        ordering = ['created_at'] # Eskiden yeniye doğru sırala
        #Yorumları kronolojik sırayla (eskiden yeniye) dizer.

    def __str__(self):
        return f"{self.author.username} - {self.ticket.title}"
        # Yorum temsil edilirken "Yazan Kullanıcı - Talep Başlığı" şeklinde metin üretir.





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
    is_read = models.BooleanField(default=False, verbose_name="Okundu Mu?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tarih")

    class Meta:
        verbose_name = "Bildirim"
        verbose_name_plural = "Bildirimler"
        ordering = ['-created_at']

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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tarih")

    class Meta:
        verbose_name = "Sohbet Mesajı"
        verbose_name_plural = "Sohbet Mesajları"
        ordering = ['created_at']

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

    def can_access_category(self, category):
        """Bu yetkilinin ilgili kategoriye erişim izni olup olmadığını denetler."""
        if self.is_superadmin:
            return True
        if not category:
            return True
        return self.assigned_categories.filter(id=category.id).exists()


from django.db.models.signals import post_save
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


class KnowledgeBaseArticle(models.Model):
    """Sıkça sorulan sorular (SSS) ve bilgi bankası makalelerini tutan model."""
    CATEGORY_CHOICES = (
        ('general', 'Genel Bilgiler'),
        ('account', 'Hesap & Güvenlik'),
        ('billing', 'Faturalandırma & Ödeme'),
        ('technical', 'Teknik Sorunlar & Hatalar'),
    )

    title = models.CharField(max_length=200, verbose_name="Makale Başlığı")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general', verbose_name="Kategori")
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
