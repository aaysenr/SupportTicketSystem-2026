from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Talep İşlemleri
    path('', views.ticket_list, name='ticket_list'), # Ana adres / geldiğinde ticket_list görünümünü çalıştır
    path('ticket/new/', views.ticket_create, name='ticket_create'), # Yeni talep oluşturma ( /ticket/new/ )
    path('ticket/<int:pk>/', views.ticket_detail, name='ticket_detail'), # Detay adresi (Örn: /ticket/1/)
    path('ticket/<int:pk>/edit/', views.ticket_edit, name='ticket_edit'), # Talep düzenleme adresi
    path('ticket/<int:pk>/delete/', views.ticket_delete, name='ticket_delete'),
    # Profil ve Şifre İşlemleri
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.change_password_view, name='change_password'),


    # Kullanıcı Kimlik Doğrulama (Auth) İşlemleri
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('verify-email/', views.verify_email, name='verify_email'),
    # İki Aşamalı Doğrulama (2FA - TOTP)
    path('2fa/setup/', views.setup_2fa_view, name='setup_2fa'),
    path('2fa/disable/', views.disable_2fa_view, name='disable_2fa'),
    path('2fa/verify/', views.verify_2fa_view, name='verify_2fa'),

    # Şifre Sıfırlama (Password Reset) Akışı
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='tickets/password_reset_form.html',
        email_template_name='tickets/password_reset_email.html',
        subject_template_name='tickets/password_reset_subject.txt',
        success_url='/password-reset/done/'
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='tickets/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='tickets/password_reset_confirm.html',
        success_url='/reset/done/'
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='tickets/password_reset_complete.html'
    ), name='password_reset_complete'),

    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'), # Yönetici Dashboard'u
    path('notifications/', views.notifications_list_view, name='notifications_list'),
    path('notifications/<int:pk>/read/', views.mark_notification_as_read, name='mark_notification_read'),




    # Ekip Sohbeti (Team Chat) İşlemleri
    path('team-chat/', views.team_chat_view, name='team_chat'),
    path('team-chat/<str:chat_type>/<int:chat_id>/', views.team_chat_view, name='team_chat_detail'),
    path('team-chat/send/', views.send_chat_message_view, name='send_chat_message'),
    path('team-chat/create-group/', views.create_chat_group_view, name='create_chat_group'),
    path('team-chat/api/messages/<str:chat_type>/<int:chat_id>/', views.get_chat_messages_api, name='get_chat_messages_api'),

    # Yorum Çözüm ve Beğeni İşlemleri
    path('comment/<int:comment_id>/solution/', views.toggle_comment_solution, name='toggle_comment_solution'),
    path('comment/<int:comment_id>/like/', views.toggle_comment_like, name='toggle_comment_like'),

    # Bilgi Bankası (Knowledge Base / FAQ) ve Canlı Öneri API'si
    path('knowledge-base/', views.knowledge_base_list_view, name='knowledge_base'),
    path('knowledge-base/<int:pk>/', views.knowledge_base_detail_view, name='knowledge_base_detail'),
    path('api/kb/suggest/', views.kb_suggest_api, name='kb_suggest_api'),

    # Hazır Yanıt Şablonları (Canned Responses) ve E-Posta Webhook API'si
    path('api/canned-responses/', views.canned_responses_api, name='canned_responses_api'),
    path('api/inbound-email/', views.inbound_email_webhook, name='inbound_email_webhook'),

    # Müşteri Memnuniyet Anketi (CSAT) Değerlendirme API'si
    path('ticket/<int:ticket_id>/rate/', views.submit_ticket_rating_api, name='ticket_rate_api'),

    # Güvenli Dosya İndirme ve Önizleme Rotaları (Yetki Kontrollü)
    path('ticket/<int:pk>/attachment/', views.download_ticket_attachment, name='ticket_attachment_download'),
    path('comment/<int:comment_id>/attachment/', views.download_comment_attachment, name='comment_attachment_download'),

    # Bildirim Toplu Okundu İşareti
    path('notifications/read-all/', views.mark_all_notifications_as_read, name='mark_all_notifications_read'),

    # Raporlama ve Dışa Aktarma (Excel / CSV)
    path('export/tickets/', views.export_tickets_csv, name='export_tickets_csv'),

    # Toplu İşlemler (Bulk Actions)
    path('tickets/bulk-action/', views.bulk_ticket_action, name='bulk_ticket_action'),
]


"""
from django.urls import path: Django'nun URL kalıplarını tanımlayan path fonksiyonunu içeri aktarır.

from . import views: Bulunduğumuz klasördeki (.) views.py dosyasını projeye dahil eder ki oradaki fonksiyonlara erişebilelim.

path('', views.ticket_list, name='ticket_list'):

'' (Boş Tırnak): Kök dizini (ana adresi) temsil eder.

views.ticket_list: Bu adrese girildiğinde views.py içindeki ticket_list fonksiyonunu tetikler.

name='ticket_list': Bu adrese verilen özel koddur/takma addır. 

İleride HTML içinde veya Python kodunda adresi elle (/) yazmak yerine {% url 'ticket_list' %} diyerek 
dinamik olarak çağırabilmemizi sağlar.


path('ticket/<int:pk>/', views.ticket_detail, name='ticket_detail'):
ticket/<int:pk>/: Dinamik URL yapısıdır. URL'deki sayıyı yakalar.
views.ticket_detail: Gelen sayıyı pk parametresi olarak alıp bu fonksiyonu tetikler.
name='ticket_detail': Bu URL kuralına verilen takma isimdir. HTML şablonlarında {% url 'ticket_detail' ticket.id %} şeklinde dinamik link oluşturmamızı sağlar.




path('ticket/new/', views.ticket_create, name='ticket_create'): 
Tarayıcıdan [http://127.0.0.1:8000/ticket/new/](http://127.0.0.1:8000/ticket/new/) 
adresine bir istek geldiğinde, views.py içerisindeki ticket_create fonksiyonunu tetikler.
 name='ticket_create' takma adı sayesinde HTML şablonlarında {% url 'ticket_create' %} yazarak bu sayfaya dinamik link verebiliriz.



path('ticket/<int:pk>/edit/', views.ticket_edit, name='ticket_edit'):

Tarayıcıdan gelen [http://127.0.0.1:8000/ticket/1/edit/](http://127.0.0.1:8000/ticket/1/edit/) gibi istekleri karşılar.

<int:pk> parçası düzenlenecek talebin ID numarasını yakalar ve views.py içerisindeki ticket_edit(request, pk) fonksiyonuna aktarır.

name='ticket_edit' takma adı sayesinde HTML şablonlarında {% url 'ticket_edit' ticket.id %} yazarak düzenleme sayfasına dinamik bağlantı vermeyi sağlar.



URL Yapısının Sıralama Mantığı:

ticket/new/: Sabit metin kuralı en üstte yer alır.

ticket/<int:pk>/: Sadece sayısal ID içeren detay sayfalarını yakalar.

ticket/<int:pk>/edit/: Sayısal ID ve ardından gelen /edit/ son ekini yakalayarak düzenleme ekranına yönlendirir. Çakışma olmadan her üç adres de bağımsız çalışır.



# AUTH KISMI:
path('register/', ... name='register'):

Tarayıcıdan /register/ adresine gidildiğinde views.register_user çalışır ve register.html formunu ekrana basar.

Şablonlarda {% url 'register' %} yazılarak dinamik link verilir.

path('login/', ... name='login'):

/login/ adresi views.login_user görünümünü tetikler. Kullanıcı adı ve şifre doğrulanır.

@login_required ile kilitli bir sayfaya yetkisiz girildiğinde veya çıkış yapıldığında kullanıcı buraya yönlendirilir.

path('logout/', ... name='logout'):

/logout/ adresi oturumu sonlandırıp kullanıcıyı tekrar login ekranına atar




Dinamik Parametre (<int:pk>): URL'deki sayısal ID'yi yakalar (Örn: /ticket/4/delete/ için pk=4) ve views.ticket_delete(request, pk) fonksiyonuna iletir.
İsimlendirme:
 (name='ticket_delete'): Şablonlarda {% url 'ticket_delete' ticket.id %} şeklinde temiz, dinamik bağlantılar oluşturmayı sağlar.
 URL Sıralama Mantığı:
 ticket/new/ ---- Statik kural
 ticket/<int:pk>/ ----- Detay kuralı
 ticket/<int:pk>/edit/ ----- Düzenleme kuralı
 ticket/<int:pk>/delete/ ------- Silme onay kuralı


"""