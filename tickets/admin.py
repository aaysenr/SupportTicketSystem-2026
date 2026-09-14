from django.contrib import admin
from .models import (
    Category, Ticket, TicketComment, UserProfile, KnowledgeBaseArticle,
    TicketRating, CannedResponse, TicketTag, TicketActivityLog,
    Notification, ChatGroup, ChatMessage, UserChatPreference, EmailVerification
)

@admin.register(TicketTag)
class TicketTagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'color', 'created_at')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


# 1. Kategori Modeli Yönetimi

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)


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


@admin.register(TicketActivityLog)
class TicketActivityLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'actor', 'action', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('ticket__title', 'action', 'actor__username')
    readonly_fields = ('ticket', 'actor', 'action', 'created_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'actor', 'ticket', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('recipient__username', 'actor__username', 'message')


@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_general', 'created_by', 'created_at')
    list_filter = ('is_general', 'created_at')
    search_fields = ('name', 'created_by__username')
    filter_horizontal = ('members',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'group', 'recipient', 'short_content', 'is_read', 'is_edited', 'is_deleted', 'created_at')
    list_filter = ('is_read', 'is_edited', 'is_deleted', 'created_at')
    search_fields = ('sender__username', 'recipient__username', 'content')

    def short_content(self, obj):
        return (obj.content[:50] + "...") if len(obj.content) > 50 else obj.content
    short_content.short_description = "İçerik"


@admin.register(UserChatPreference)
class UserChatPreferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'group', 'dm_user', 'is_archived', 'cleared_at')
    list_filter = ('is_archived',)
    search_fields = ('user__username', 'dm_user__username')


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'code', 'failed_attempts', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email', 'code')
