from django.db import models
from django.contrib.auth.models import User


# İçe Aktarmalar (Imports)
# from django.db import models: Django'nun veritabanı yönetim araçlarını ve sütun tiplerini (CharField, ForeignKey vb.) projeye dahil eder.
# from django.contrib.auth.models import User: Django'nun hazır kullanıcı yönetimi modelini projeye aktarır.


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

    class Meta:
        #Yorumlara ait genel ayarlar
        verbose_name = "Yorum"
        verbose_name_plural = "Yorumlar"
        ordering = ['created_at'] # Eskiden yeniye doğru sırala
        #Yorumları kronolojik sırayla (eskiden yeniye) dizer.

    def __str__(self):
        return f"{self.author.username} - {self.ticket.title}"
        # Yorum temsil edilirken "Yazan Kullanıcı - Talep Başlığı" şeklinde metin üretir.
