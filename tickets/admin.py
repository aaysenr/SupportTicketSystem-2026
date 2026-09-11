from django.contrib import admin
from .models import Category, Ticket, TicketComment, UserProfile, KnowledgeBaseArticle, TicketRating, CannedResponse

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


# 4. Kullanıcı Profili ve Rol Yönetimi (RBAC)
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'get_categories')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')
    filter_horizontal = ('assigned_categories',)

    def get_categories(self, obj):
        cats = [c.name for c in obj.assigned_categories.all()]
        return ", ".join(cats) if cats else "-"
    get_categories.short_description = "Sorumlu Kategoriler"


from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Kullanıcı Rolü ve Departman Yetkisi (RBAC)'
    filter_horizontal = ('assigned_categories',)

# Django varsayılan User admin'ini genişletiyoruz
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


@admin.register(KnowledgeBaseArticle)
class KnowledgeBaseArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'views_count', 'is_published', 'created_at')
    list_filter = ('category', 'is_published', 'created_at')
    search_fields = ('title', 'content', 'keywords')
    list_editable = ('is_published',)


@admin.register(TicketRating)
class TicketRatingAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'user', 'score', 'created_at')
    list_filter = ('score', 'created_at')
    search_fields = ('ticket__title', 'user__username', 'feedback')


@admin.register(CannedResponse)
class CannedResponseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_by', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('title', 'content')

