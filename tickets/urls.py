from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, forms

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
        form_class=forms.CustomPasswordResetForm,
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
    path('team-chat/api/message/<int:pk>/edit/', views.edit_chat_message_view, name='edit_chat_message'),
    path('team-chat/api/message/<int:pk>/delete/', views.delete_chat_message_view, name='delete_chat_message'),
    path('team-chat/api/message/<int:pk>/star/', views.toggle_favorite_chat_message_view, name='toggle_favorite_chat_message'),
    path('team-chat/api/chat/clear/', views.clear_chat_view, name='clear_chat'),
    path('team-chat/api/chat/archive/', views.toggle_archive_chat_view, name='toggle_archive_chat'),

    # Yorum Çözüm, Beğeni, Düzenleme ve Silme İşlemleri
    path('comment/<int:comment_id>/solution/', views.toggle_comment_solution, name='toggle_comment_solution'),
    path('comment/<int:comment_id>/like/', views.toggle_comment_like, name='toggle_comment_like'),
    path('comment/<int:comment_id>/edit/', views.comment_edit, name='comment_edit'),
    path('comment/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),

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

    # Bildirim İşlemleri (Toplu Okundu, Tekil/Toplu Silme)
    path('notifications/read-all/', views.mark_all_notifications_as_read, name='mark_all_notifications_read'),
    path('notifications/<int:pk>/delete/', views.delete_notification, name='delete_notification'),
    path('notifications/delete-all/', views.delete_all_notifications, name='delete_all_notifications'),

    # Raporlama ve Dışa Aktarma (Excel / CSV & PDF)
    path('export/tickets/', views.export_tickets_csv, name='export_tickets_csv'),
    path('export/tickets/excel/', views.export_tickets_excel, name='export_tickets_excel'),
    path('ticket/<int:pk>/pdf/', views.export_ticket_pdf, name='export_ticket_pdf'),
    path('ticket/merge/', views.merge_tickets_view, name='merge_tickets'),

    # Yapay Zekâ Destekli Talep Asistanı (AI Copilot) API'leri
    path('api/ai/suggest-meta/', views.ai_suggest_meta_api, name='ai_suggest_meta_api'),
    path('api/ai/summarize/<int:pk>/', views.ai_summarize_ticket_api, name='ai_summarize_ticket_api'),

    # Toplu İşlemler (Bulk Actions)
    path('tickets/bulk-action/', views.bulk_ticket_action, name='bulk_ticket_action'),

    # Etiket Yönetimi API'leri
    path('api/tags/', views.list_tags_api, name='list_tags_api'),
    path('api/tags/create/', views.create_tag_api, name='create_tag_api'),
    path('api/tags/<int:pk>/edit/', views.edit_tag_api, name='edit_tag_api'),
    path('api/tags/<int:pk>/delete/', views.delete_tag_api, name='delete_tag_api'),
]