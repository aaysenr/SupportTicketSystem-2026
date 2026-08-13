from django.contrib import admin
from .models import Category, Ticket, TicketComment

#from django.contrib import admin: Django'nun yönetim paneli araçlarını projeye dahil eder.
#from .models import ...: Aynı klasördeki (.) models.py dosyasından hazırladığımız 3 modeli içe aktarır.



# 1. Kategori Modeli Yönetimi

@admin.register(Category)

# @admin.register(...): Python'da Decorator (Dekoratör) olarak adlandırılır.

# Modeli admin paneline kaydetmek için eski yöntem olan admin.site.register(Category, CategoryAdmin) yazmak yerine, 
# sınıfın hemen üzerine bu etiketi koyarak modeli ve ona ait yönetim ayarlarını birbirine bağlarız.


class CategoryAdmin(admin.ModelAdmin):
    # class CategoryAdmin(admin.ModelAdmin): Django'nun temel ModelAdmin sınıfından miras alarak
    # Category tablosunun admin panelindeki görünüm kurallarını yazarız.

    list_display = ('id', 'name', 'description') # Admin listesinde görünecek sütunlar
    #Admin panelinde kategoriler listelendiğinde ekranda tablo sütunu olarak nelerin görüneceğini belirler (ID, Kategori Adı ve Açıklama).

    
    search_fields = ('name',) # Kategori ismine göre arama kutusu
    #Arama kutusu ekleyerek admin panelinde kategori adlarına göre hızlı arama yapma imkanı sunar.
    #Admin panelinin üst tarafına bir Arama Kutusu ekler. 
    # Yönetici bir şey arattığında Django aramayı kategorinin name alanında yapar. 
    # (Virgüle dikkat: Tek elemanlı bir demet/tuple olduğu için sonuna virgül koyulur).
    #Admin panelinde arama kutusunun yanındaki filtreleme butonlarının hangi alanlara göre açılacağını belirler.
    #Admin panelinde listelenen verilerin durum, öncelik, kategori ve oluşturulma tarihine göre filtreleme yapma imkanı sunar.
    #Admin panelinde listelenen verilerin durum ve önceliğine göre doğrudan düzenleme yapma imkanı sunar.

# 2. Destek Talebi Modeli Yönetimi

@admin.register(Ticket)

# @admin.register(...): Python'da Decorator (Dekoratör) olarak adlandırılır.

# Modeli admin paneline kaydetmek için eski yöntem olan admin.site.register(Category, CategoryAdmin) yazmak yerine, 
# sınıfın hemen üzerine bu etiketi koyarak modeli ve ona ait yönetim ayarlarını birbirine bağlarız.


class TicketAdmin(admin.ModelAdmin):
    # class CategoryAdmin(admin.ModelAdmin): Django'nun temel ModelAdmin sınıfından miras alarak
    # Category tablosunun admin panelindeki görünüm kurallarını yazarız.

    list_display = ('id', 'title', 'category', 'priority', 'status', 'created_by', 'created_at') # Kolonlar
    #Talepler listesinde ID, Başlık, Kategori, Öncelik, Durum, Oluşturan Kullanıcı ve Tarih sütunlarını gösterir.
    list_filter = ('status', 'priority', 'category', 'created_at') # Sağ taraftaki filtre paneli
    #Admin panelinin sağ tarafında Filtreleme Paneli (Sidebar) oluşturur. Tıklayarak "Sadece Açık olanlar", "Sadece Yüksek Öncelikliler" veya "Belirli bir kategoridekiler" anında süzülebilir.
    search_fields = ('title', 'description') # Başlık ve açıklamada arama
    #Arama kutusuna yazılan kelimeyi hem talep başlığında (title) hem de açıklamasında (description) arar.
    list_editable = ('status', 'priority') # Doğrudan listeden durum/öncelik değiştirebilme kolaylığı
    # Çok pratik bir özelliktir! Detay sayfasına girmeden, doğrudan liste ekranı üzerinden talebin durumunu (status) veya önceliğini (priority) değiştirip kaydetmeyi sağlar.

# 3. Yorum Modeli Yönetimi
@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'author', 'created_at')
    #Yorum listesinde ID, Talep, Yazar ve Oluşturulma Tarihi sütunlarını gösterir.
    search_fields = ('content',)
    #Yorum içeriği üzerinden arama yapar.
    list_filter = ('created_at',)
    #Yorumların tarihine göre filtreleme yapma imkanı sunar.    
