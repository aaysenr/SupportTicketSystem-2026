import random
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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

    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Öncelik")
    #Öncelik seviyesi sütunudur. choices ile tanımlanan seçenekler dışına çıkılamaz, varsayılan değeri (default) 'medium' yani "Orta"dır.
    # max_length=20: Maksimum 20 karakter uzunluğunda metin sütunu oluşturur.
    # choices=PRIORITY_CHOICES: Seçenekler PRIORITY_CHOICES demetinden gelir.
    # default='medium': Varsayılan değer "medium" olarak ayarlanır.
    # verbose_name: Formlarda ve adminde "Öncelik" olarak görünür.

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name="Durum")
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
        verbose_name="Dosya / Görsel Eki" # admin panelinde görünecek başlık
    )

    
    is_public = models.BooleanField(
        default=False, 
        verbose_name="Herkese Açık (Topluluk / Forum Talebi)",
        help_text="İşaretlenirse tüm kullanıcılar bu talebi ve çözümünü görebilir. İşaretlenmezse sadece yöneticiler görebilir."
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

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tarih")
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
        verbose_name="Dosya / Görsel Eki"  # admin panelinde görünecek başlık
    )
   
    '''
    upload_to sayesinde dosyalar tarih bazlı klasörlenir. 
    blank=True, null=True dosya yüklemenin zorunlu olmadığını belirtir.
    ''' 

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
