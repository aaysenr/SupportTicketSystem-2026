from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.urls import reverse
from io import StringIO
from django.core.management import call_command
from django.conf import settings
from tickets.models import Category, Ticket, TicketComment, UserProfile, KnowledgeBaseArticle, TicketRating, Notification, ChatGroup, ChatMessage, EmailVerification, CannedResponse
from tickets.validators import validate_file_security
from tickets.totp import generate_totp_secret, get_totp_token, verify_totp_token
from django.utils import timezone
from datetime import timedelta


class SecurityAndRBACWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Kullanıcılar
        self.super_user = User.objects.create_superuser('superadmin', 'admin@example.com', 'AdminPass123!')
        self.tech_user = User.objects.create_user('tech_agent', 'tech@example.com', 'TechPass123!', is_staff=True)
        self.fin_user = User.objects.create_user('fin_agent', 'fin@example.com', 'FinPass123!', is_staff=True)
        self.normal_user = User.objects.create_user('john_doe', 'john@example.com', 'UserPass123!')

        # Kategoriler
        self.cat_tech = Category.objects.create(name='Teknik Destek')
        self.cat_fin = Category.objects.create(name='Finans')

        # RBAC Rol ve Kategori Atamaları
        self.tech_user.profile.role = 'support_agent'
        self.tech_user.profile.assigned_categories.add(self.cat_tech)
        self.tech_user.profile.save()

        self.fin_user.profile.role = 'finance_agent'
        self.fin_user.profile.assigned_categories.add(self.cat_fin)
        self.fin_user.profile.save()

        # Talepler
        self.ticket_tech = Ticket.objects.create(
            title='Yazıcı Arızası',
            description='Yazıcı çıktısı alınamıyor.',
            category=self.cat_tech,
            created_by=self.normal_user,
            is_public=False
        )
        self.ticket_fin = Ticket.objects.create(
            title='Fatura Düzeltme',
            description='Faturam hatalı kesilmiş.',
            category=self.cat_fin,
            created_by=self.normal_user,
            is_public=False
        )

    # 1. DOSYA GÜVENLİĞİ TESTLERİ
    def test_file_size_limit_validation(self):
        """10 MB üzeri dosyaların engellendiğini doğrula."""
        large_content = b'x' * (11 * 1024 * 1024)  # 11 MB
        large_file = SimpleUploadedFile("big_file.pdf", large_content, content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_file_security(large_file)

    def test_file_extension_validation(self):
        """Zararlı / izinsiz uzantıların (.exe, .bat, .php) engellendiğini doğrula."""
        bad_file = SimpleUploadedFile("malware.exe", b"malicious content", content_type="application/x-msdownload")
        with self.assertRaises(ValidationError):
            validate_file_security(bad_file)

    def test_valid_file_passes(self):
        """İzin verilen uzantıların (.png, .pdf, .log vb.) başarıyla geçtiğini doğrula."""
        good_file = SimpleUploadedFile("document.pdf", b"%PDF-1.4 sample", content_type="application/pdf")
        try:
            validate_file_security(good_file)
        except ValidationError:
            self.fail("Geçerli dosya ValidationError fırlatmamalı!")

    # 2. ŞİFRE SIFIRLAMA (PASSWORD RESET) ROTASI TESTLERİ
    def test_password_reset_views_load(self):
        """Şifre sıfırlama ekranlarının başarıyla yüklendiğini teyit et."""
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tickets/password_reset_form.html')

        response = self.client.get(reverse('password_reset_done'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tickets/password_reset_done.html')

        response = self.client.get(reverse('password_reset_complete'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tickets/password_reset_complete.html')

    # 3. RBAC (ROL TABANLI ERİŞİM) TESTLERİ
    def test_tech_agent_sees_only_tech_tickets(self):
        """Teknik destek yetkilisinin yalnızca kendi biriminin taleplerini gördüğünü test et."""
        self.client.login(username='tech_agent', password='TechPass123!')
        response = self.client.get(reverse('ticket_list'))
        self.assertEqual(response.status_code, 200)
        tickets = response.context['tickets'].object_list
        self.assertIn(self.ticket_tech, tickets)
        self.assertNotIn(self.ticket_fin, tickets)

    def test_finance_agent_sees_only_finance_tickets(self):
        """Finans yetkilisinin yalnızca finans kategorisindeki talepleri gördüğünü test et."""
        self.client.login(username='fin_agent', password='FinPass123!')
        response = self.client.get(reverse('ticket_list'))
        self.assertEqual(response.status_code, 200)
        tickets = response.context['tickets'].object_list
        self.assertIn(self.ticket_fin, tickets)
        self.assertNotIn(self.ticket_tech, tickets)

    def test_superadmin_sees_all_tickets(self):
        """Süper yöneticinin tüm birimlerin taleplerini eksiksiz gördüğünü test et."""
        self.client.login(username='superadmin', password='AdminPass123!')
        response = self.client.get(reverse('ticket_list'))
        self.assertEqual(response.status_code, 200)
        tickets = response.context['tickets'].object_list
        self.assertIn(self.ticket_tech, tickets)
        self.assertIn(self.ticket_fin, tickets)

    def test_rbac_detail_view_access_restriction(self):
        """Finans yetkilisinin başka birimin (Teknik Destek) özel talebine erişiminin engellendiğini test et."""
        self.client.login(username='fin_agent', password='FinPass123!')
        response = self.client.get(reverse('ticket_detail', kwargs={'pk': self.ticket_tech.pk}))
        # Yetkisiz erişimde mesaj verilerek ticket_list sayfasına yönlendirilir (302 Redirect)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('ticket_list'))

    # 4. YORUM BEĞENİ VE ÇÖZÜM İŞARETLEME (VE GERİ ALMA) TESTLERİ
    def test_toggle_comment_solution_and_undo(self):
        """Yorumu çözüm işaretleme ve geri alma durumunu test et (Yalnızca POST kabul edilmeli)."""
        comment = TicketComment.objects.create(ticket=self.ticket_tech, author=self.tech_user, content="Çözüm adımı")
        self.client.login(username='superadmin', password='AdminPass123!')
        url = reverse('toggle_comment_solution', kwargs={'comment_id': comment.id})

        # GET isteği 405 (Method Not Allowed) dönmeli (CSRF güvenliği)
        res_get = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_get.status_code, 405)

        # 1. POST ile çözüm olarak işaretle
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['is_solution'])
        self.assertEqual(data['ticket_status'], 'resolved')

        # 2. Geri Al (Undo): Çözüm işaretini kaldır
        response_undo = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_ACCEPT='application/json')
        self.assertEqual(response_undo.status_code, 200)
        data_undo = response_undo.json()
        self.assertEqual(data_undo['status'], 'ok')
        self.assertFalse(data_undo['is_solution'])
        self.assertEqual(data_undo['ticket_status'], 'in_progress')

    def test_toggle_comment_like_and_undo(self):
        """Yorumu beğenme ve beğeniyi geri alma durumunu test et (Yalnızca POST kabul edilmeli)."""
        comment = TicketComment.objects.create(ticket=self.ticket_tech, author=self.tech_user, content="Faydalı yorum")
        self.client.login(username='john_doe', password='UserPass123!')
        url = reverse('toggle_comment_like', kwargs={'comment_id': comment.id})

        # GET isteği 405 (Method Not Allowed) dönmeli
        res_get = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_get.status_code, 405)

        # 1. POST ile beğen (Faydalı bul)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['liked'])
        self.assertEqual(data['like_count'], 1)

        # 2. Geri Al (Undo): Beğeniyi kaldır
        response_undo = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_ACCEPT='application/json')
        self.assertEqual(response_undo.status_code, 200)
        data_undo = response_undo.json()
        self.assertEqual(data_undo['status'], 'ok')
        self.assertFalse(data_undo['liked'])
        self.assertEqual(data_undo['like_count'], 0)

    # 5. SLA & YANIT SÜRESİ TAKİBİ TESTLERİ
    def test_sla_target_hours_and_properties(self):
        """Öncelik bazlı SLA saatlerini ve gecikme hesaplamalarını test et."""
        urgent_ticket = Ticket.objects.create(
            title='Sistem Çöktü',
            description='Hemen müdahale gerek.',
            priority='urgent',
            created_by=self.normal_user
        )
        self.assertEqual(urgent_ticket.sla_target_hours, 2)
        self.assertIsNotNone(urgent_ticket.sla_deadline)

        # Mesai saatleri duyarlı SLA testi:
        # Hafta içi mesai saatinde açılmış geçmiş bir talep
        test_created = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=1)
        while test_created.weekday() in (5, 6):
            test_created -= timedelta(days=1)
        urgent_ticket.created_at = test_created
        urgent_ticket.save()
        self.assertTrue(urgent_ticket.is_sla_breached)

    def test_sla_first_response_tracking_on_staff_comment(self):
        """Yetkili yorum yaptığında ticket.first_response_at alanının dolduğunu test et."""
        self.client.login(username='tech_agent', password='TechPass123!')
        self.assertIsNone(self.ticket_tech.first_response_at)

        url = reverse('ticket_detail', kwargs={'pk': self.ticket_tech.pk})
        response = self.client.post(url, {
            'content': 'Talebiniz inceleniyor, kontroller başladı.'
        })
        self.assertEqual(response.status_code, 302)

        self.ticket_tech.refresh_from_db()
        self.assertIsNotNone(self.ticket_tech.first_response_at)

    # 6. BİLGİ BANKASI (SSS) & CANLI ÖNERİ API TESTLERİ
    def test_knowledge_base_views_and_suggest_api(self):
        """Bilgi Bankası listeleme, detay ve canlı suggest API'sini test et."""
        article = KnowledgeBaseArticle.objects.create(
            title='E-Posta Kurulum Rehberi',
            category=self.cat_tech,
            content='Outlook ve Thunderbird kurulum parametreleri...',
            keywords='mail, eposta, imap, pop3'
        )

        # 1. Bilgi Bankası Listeleme Ekranı
        response = self.client.get(reverse('knowledge_base'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'E-Posta Kurulum Rehberi')

        # 2. Makale Detay Ekranı
        detail_url = reverse('knowledge_base_detail', kwargs={'pk': article.pk})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, 'Outlook ve Thunderbird')

        # 3. Canlı Öneri API (kb_suggest_api)
        api_url = reverse('kb_suggest_api') + '?q=Kurulum'
        res_api = self.client.get(api_url)
        self.assertEqual(res_api.status_code, 200)
        data = res_api.json()
        self.assertIn('suggestions', data)
        self.assertTrue(any(s['title'] == 'E-Posta Kurulum Rehberi' for s in data['suggestions']))

    # 7. MÜŞTERİ MEMNUNİYET ANKETİ (CSAT) TESTLERİ
    def test_ticket_csat_rating_workflow(self):
        """Çözülen talep için 1-5 yıldız CSAT değerlendirmesini test et."""
        # Talebi çözüldü yap
        self.ticket_tech.status = 'resolved'
        self.ticket_tech.save()

        rate_url = reverse('ticket_rate_api', kwargs={'ticket_id': self.ticket_tech.id})

        # 1. Giriş yapmamış kullanıcı erişemez (302 login redirect)
        res_unauth = self.client.post(rate_url, {'score': 5, 'feedback': 'Mükemmel'})
        self.assertEqual(res_unauth.status_code, 302)

        # 2. Talep sahibi giriş yapıp 5 yıldız verir
        self.client.login(username='john_doe', password='UserPass123!')
        res_rate = self.client.post(rate_url, {'score': 5, 'feedback': 'Hızlı ve başarılı destek!'})
        self.assertEqual(res_rate.status_code, 200)
        data = res_rate.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['score'], 5)

        # Veritabanında TicketRating oluştuğunu teyit et
        rating = TicketRating.objects.get(ticket=self.ticket_tech)
        self.assertEqual(rating.score, 5)
        self.assertEqual(rating.user, self.normal_user)

    # 8. GELİŞMİŞ GÜVENLİK & YETKİLENDİRME (SECTION A) TESTLERİ
    def test_ticket_delete_rbac_permission_restrictions(self):
        """Silme yetkisinin yalnızca yetkili veya sorumlu departman personeliyle sınırlandığını test et."""
        delete_url = reverse('ticket_delete', kwargs={'pk': self.ticket_tech.pk})

        # 1. Talebin sahibi olmayan başka bir normal kullanıcı silemez (302 redirect ve hata mesajı)
        other_user = User.objects.create_user(username='other_normal', password='UserPass123!')
        self.client.login(username='other_normal', password='UserPass123!')
        res_user = self.client.post(delete_url)
        self.assertEqual(res_user.status_code, 302)
        self.assertTrue(Ticket.objects.filter(pk=self.ticket_tech.pk).exists())

        # 2. Finans yetkilisi, Teknik Destek talebini silemez (RBAC İzolasyonu)
        self.client.login(username='fin_agent', password='FinPass123!')
        res_fin = self.client.post(delete_url)
        self.assertEqual(res_fin.status_code, 302)
        self.assertTrue(Ticket.objects.filter(pk=self.ticket_tech.pk).exists())

        # 3. Teknik destek yetkilisi kendi biriminin talebini silebilir
        self.client.login(username='tech_agent', password='TechPass123!')
        res_tech = self.client.post(delete_url)
        self.assertEqual(res_tech.status_code, 302)
        self.assertFalse(Ticket.objects.filter(pk=self.ticket_tech.pk).exists())

    def test_secure_ticket_attachment_download_permissions(self):
        """Özel taleplerin ek dosyalarına yetkisiz erişimin engellendiğini test et."""
        # Ek dosya ekle
        sample_file = SimpleUploadedFile("secret.pdf", b"%PDF-secret data", content_type="application/pdf")
        self.ticket_fin.attachment = sample_file
        self.ticket_fin.save()

        download_url = reverse('ticket_attachment_download', kwargs={'pk': self.ticket_fin.pk})

        # 1. Giriş yapmamış kullanıcı giriş sayfasına yönlendirilir (302)
        res_anon = self.client.get(download_url)
        self.assertEqual(res_anon.status_code, 302)

        # 2. Yetkisiz personel (Teknik personeli, Finans talebini indiremez -> 403 Forbidden)
        self.client.login(username='tech_agent', password='TechPass123!')
        res_unauth = self.client.get(download_url)
        self.assertEqual(res_unauth.status_code, 403)

        # 3. Talebi açan kullanıcı (veya finans personeli) indirebilir -> 200 OK
        self.client.login(username='john_doe', password='UserPass123!')
        res_owner = self.client.get(download_url)
        self.assertEqual(res_owner.status_code, 200)

    # 9. FONKSİYONEL & OPERASYONEL (SECTION B) TESTLERİ
    def test_mark_all_notifications_read(self):
        """Kullanıcının tüm okunmamış bildirimlerini tek tıkla okundu olarak işaretleyebildiğini test et."""
        # Normal kullanıcı için 2 bildirim oluştur
        notif1 = Notification.objects.create(recipient=self.normal_user, ticket=self.ticket_tech, message="Bildirim 1")
        notif2 = Notification.objects.create(recipient=self.normal_user, ticket=self.ticket_tech, message="Bildirim 2")
        # Finans kullanıcısı için 1 bildirim oluştur
        notif_fin = Notification.objects.create(recipient=self.fin_user, ticket=self.ticket_fin, message="Finans Bildirimi")

        self.assertEqual(Notification.objects.filter(recipient=self.normal_user, is_read=False).count(), 2)

        # Giriş yapıp 'tümünü okundu yap' çağır
        self.client.login(username='john_doe', password='UserPass123!')
        url = reverse('mark_all_notifications_read')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        # Normal kullanıcının tüm bildirimleri okunmuş olmalı
        self.assertEqual(Notification.objects.filter(recipient=self.normal_user, is_read=False).count(), 0)
        # Başka kullanıcının bildirimi okunmamış kalmalı (İzolasyon)
        notif_fin.refresh_from_db()
        self.assertFalse(notif_fin.is_read)

    def test_export_tickets_csv_permissions_and_format(self):
        """Excel/CSV dışa aktarımının sadece yetkililere açık olduğunu ve formatını test et."""
        export_url = reverse('export_tickets_csv')

        # 1. Normal kullanıcı dışa aktaramaz (302 redirect ve yetki mesajı)
        self.client.login(username='john_doe', password='UserPass123!')
        res_user = self.client.get(export_url)
        self.assertEqual(res_user.status_code, 302)

        # 2. Yetkili kullanıcı dışa aktarabilir
        self.client.login(username='tech_agent', password='TechPass123!')
        res_staff = self.client.get(export_url)
        self.assertEqual(res_staff.status_code, 200)
        self.assertEqual(res_staff['Content-Type'], 'text/csv; charset=utf-8-sig')
        self.assertIn('attachment; filename="destek_talepleri_raporu_', res_staff['Content-Disposition'])
        
        # İçerik kontrolü
        content = res_staff.content.decode('utf-8-sig')
        self.assertIn('Talep No;Başlık;Kategori', content)
        self.assertIn('Yazıcı Arızası', content)

    def test_bulk_ticket_actions(self):
        """Toplu işlem (bulk action) ile durum, atanan ve kategori güncellemesini test et."""
        bulk_url = reverse('bulk_ticket_action')

        # 1. Normal kullanıcı toplu işlem yapamaz
        self.client.login(username='john_doe', password='UserPass123!')
        res_user = self.client.post(bulk_url, {
            'bulk_action': 'status',
            'bulk_target_value': 'closed',
            'selected_tickets': [self.ticket_tech.id]
        })
        self.assertEqual(res_user.status_code, 302)
        self.ticket_tech.refresh_from_db()
        self.assertNotEqual(self.ticket_tech.status, 'closed')

        # 2. Departman yetkilisi sadece kendi kategorisindeki talepleri toplu güncelleyebilir (RBAC İzolasyonu)
        self.client.login(username='tech_agent', password='TechPass123!')
        res_bulk_status = self.client.post(bulk_url, {
            'bulk_action': 'status',
            'bulk_target_value': 'closed',
            'selected_tickets': [self.ticket_tech.id, self.ticket_fin.id]
        })
        self.assertEqual(res_bulk_status.status_code, 302)
        self.ticket_tech.refresh_from_db()
        self.ticket_fin.refresh_from_db()
        self.assertEqual(self.ticket_tech.status, 'closed')
        # Finans talebine teknik personeli dokunamaz
        self.assertEqual(self.ticket_fin.status, 'open')

        # 3. Süper yönetici tüm talepleri toplu güncelleyebilir
        self.client.login(username='superadmin', password='AdminPass123!')
        res_super_status = self.client.post(bulk_url, {
            'bulk_action': 'status',
            'bulk_target_value': 'closed',
            'selected_tickets': [self.ticket_fin.id]
        })
        self.assertEqual(res_super_status.status_code, 302)
        self.ticket_fin.refresh_from_db()
        self.assertEqual(self.ticket_fin.status, 'closed')

        # 4. Toplu atama (assign) testi
        res_bulk_assign = self.client.post(bulk_url, {
            'bulk_action': 'assign',
            'bulk_target_value': str(self.tech_user.id),
            'selected_tickets': [self.ticket_tech.id]
        })
        self.assertEqual(res_bulk_assign.status_code, 302)
        self.ticket_tech.refresh_from_db()
        self.assertEqual(self.ticket_tech.assigned_to, self.tech_user)

        # 5. Toplu kategori değiştirme testi
        res_bulk_cat = self.client.post(bulk_url, {
            'bulk_action': 'category',
            'bulk_target_value': str(self.cat_fin.id),
            'selected_tickets': [self.ticket_tech.id]
        })
        self.assertEqual(res_bulk_cat.status_code, 302)
        self.ticket_tech.refresh_from_db()
        self.assertEqual(self.ticket_tech.category, self.cat_fin)

    # 10. ALTYAPI & PERFORMANS (SECTION C) TESTLERİ
    def test_production_infrastructure_settings(self):
        """ASGI, Channels ve veritabanı ayarlarının doğruluğunu test et."""
        self.assertEqual(settings.ASGI_APPLICATION, 'config.asgi.application')
        self.assertIn('default', settings.CHANNEL_LAYERS)
        self.assertIn('daphne', settings.INSTALLED_APPS)
        self.assertIn('channels', settings.INSTALLED_APPS)

    def test_send_test_email_command(self):
        """send_test_email yönetim komutunun çalıştığını ve e-posta gönderdiğini test et."""
        out = StringIO()
        call_command('send_test_email', 'yonetici@example.com', stdout=out)
        output = out.getvalue()
        self.assertIn('E-Posta Servisi Test Ediliyor...', output)
        self.assertIn('yonetici@example.com', output)

    def test_team_chat_delta_polling_api(self):
        """Ekip sohbeti API'sinde ?after_id ile yalnızca yeni mesajların çekilmesini test et."""
        group = ChatGroup.objects.create(name='Operasyon Ekibi', created_by=self.tech_user)
        group.members.add(self.tech_user)

        msg1 = ChatMessage.objects.create(sender=self.tech_user, group=group, content="Mesaj 1")
        msg2 = ChatMessage.objects.create(sender=self.tech_user, group=group, content="Mesaj 2")
        msg3 = ChatMessage.objects.create(sender=self.tech_user, group=group, content="Mesaj 3")

        self.client.login(username='tech_agent', password='TechPass123!')

        # 1. after_id olmadan tüm mesajlar gelir (3 adet)
        url_all = reverse('get_chat_messages_api', kwargs={'chat_type': 'group', 'chat_id': group.id})
        res_all = self.client.get(url_all)
        self.assertEqual(res_all.status_code, 200)
        data_all = res_all.json()
        self.assertEqual(len(data_all['messages']), 3)

        # 2. after_id=msg2.id verildiğinde yalnızca msg3 gelir (Delta polling)
        url_delta = f"{url_all}?after_id={msg2.id}"
        res_delta = self.client.get(url_delta)
        self.assertEqual(res_delta.status_code, 200)
        data_delta = res_delta.json()
        self.assertEqual(len(data_delta['messages']), 1)
        self.assertEqual(data_delta['messages'][0]['content'], "Mesaj 3")
        self.assertEqual(data_delta['messages'][0]['message_id'], msg3.id)

    # 11. GÜVENLİK VE YETKİLENDİRME (1.1 - 1.8) YENİ TESTLERİ
    def test_ticket_form_xss_sanitization(self):
        """TicketForm açıklama alanının zararlı script ve event handler etiketlerinden arındırıldığını test et."""
        from tickets.forms import TicketForm
        form_data = {
            'title': 'XSS Güvenlik Testi',
            'description': '<script>alert("hacked")</script><p>Normal metin</p><img src="x" onerror="alert(1)">',
            'priority': 'medium',
            'status': 'open',
            'category': self.cat_tech.id,
        }
        form = TicketForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        cleaned_desc = form.cleaned_data['description']
        self.assertNotIn('<script>', cleaned_desc)
        self.assertNotIn('alert(', cleaned_desc)
        self.assertNotIn('onerror', cleaned_desc)
        self.assertIn('<p>Normal metin</p>', cleaned_desc)

    def test_ticket_delete_permissions(self):
        """Kullanıcının kendi açık talebini silebilmesi, kapalı veya başkasının talebini silememesi test edilir."""
        # John_doe kendi açık talebi
        user_ticket = Ticket.objects.create(
            title='John Kendi Talebi',
            description='Açık durumdaki talep',
            status='open',
            created_by=self.normal_user,
            category=self.cat_tech
        )
        self.client.login(username='john_doe', password='UserPass123!')
        del_url = reverse('ticket_delete', kwargs={'pk': user_ticket.pk})

        # Kendi açık talebini silebilir (302 redirect to ticket_list)
        res = self.client.post(del_url)
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Ticket.objects.filter(pk=user_ticket.pk).exists())

        # Başkasının talebini silemez
        other_ticket = Ticket.objects.create(
            title='Tech Agent Talebi',
            description='Teknik talep',
            status='open',
            created_by=self.tech_user,
            category=self.cat_tech
        )
        res_fail = self.client.post(reverse('ticket_delete', kwargs={'pk': other_ticket.pk}))
        self.assertEqual(res_fail.status_code, 302)
        self.assertTrue(Ticket.objects.filter(pk=other_ticket.pk).exists())

        # Kendi kapalı talebini silemez
        closed_ticket = Ticket.objects.create(
            title='John Kapalı Talebi',
            description='Kapanmış talep',
            status='closed',
            created_by=self.normal_user,
            category=self.cat_tech
        )
        res_closed = self.client.post(reverse('ticket_delete', kwargs={'pk': closed_ticket.pk}))
        self.assertEqual(res_closed.status_code, 302)
        self.assertTrue(Ticket.objects.filter(pk=closed_ticket.pk).exists())

    def test_email_verification_failed_attempts_and_resend(self):
        """E-posta doğrulama OTP kodu için 5 hatalı deneme sınırı ve yeni kod üretme test edilir."""
        test_user = User.objects.create_user(username='otp_test_user', email='otp@test.com', password='TestPassword123!', is_active=False)
        verification = EmailVerification.objects.create(user=test_user)
        valid_code = verification.code

        # Oturumda unverified_user_id tanımla
        session = self.client.session
        session['unverified_user_id'] = test_user.id
        session.save()

        verify_url = reverse('verify_email')

        # 5 kez yanlış kod girilsin
        for i in range(5):
            self.client.post(verify_url, {'code': '000000'})
        
        verification.refresh_from_db()
        self.assertEqual(verification.failed_attempts, 5)

        # 6. denemede doğru kod bile girilse kilitlenmeli
        self.client.post(verify_url, {'code': valid_code})
        test_user.refresh_from_db()
        self.assertFalse(test_user.is_active)

        # Yeni kod talep et (action=resend)
        res_resend = self.client.post(verify_url, {'action': 'resend'})
        self.assertEqual(res_resend.status_code, 302)
        verification.refresh_from_db()
        self.assertEqual(verification.failed_attempts, 0)
        self.assertNotEqual(verification.code, '000000')

        # Şimdi yeni üretilen kod ile başarılı onaylama
        res_success = self.client.post(verify_url, {'code': verification.code})
        self.assertEqual(res_success.status_code, 302)
        test_user.refresh_from_db()
        self.assertTrue(test_user.is_active)

    # 12. PERFORMANS VE VERİTABANI OPTİMİZASYONLARI (2.1 - 2.5) TESTLERİ
    def test_dashboard_metrics_aggregation_and_sla_breach(self):
        """Dashboard metriklerinin koşullu toplama ve veritabanı SLA sorgusu ile doğru hesaplandığını test et."""
        self.client.login(username='superadmin', password='AdminPass123!')
        res = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('total_tickets', res.context)
        self.assertIn('sla_breached_count', res.context)
        self.assertIn('sla_breached_tickets', res.context)
        self.assertGreaterEqual(res.context['total_tickets'], 2)

    def test_ticket_list_conditional_aggregation_counts(self):
        """Talep listesindeki sayaçların tekil aggregate sorgusuyla doğru geldiğini test et."""
        self.client.login(username='superadmin', password='AdminPass123!')
        res = self.client.get(reverse('ticket_list'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('total_count', res.context)
        self.assertIn('open_count', res.context)
        self.assertGreaterEqual(res.context['total_count'], 2)

    def test_knowledge_base_atomic_views_count_increment(self):
        """Bilgi bankası makale sayacının F() ifadesiyle atomik arttığını test et."""
        article = KnowledgeBaseArticle.objects.create(
            title='Test Makalesi',
            content='Test makale içeriği',
            category=self.cat_tech,
            is_published=True,
            views_count=0
        )
        url = reverse('knowledge_base_detail', kwargs={'pk': article.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.views_count, 1)

    def test_comment_with_update_text_not_hidden(self):
        """Kullanıcının 'Güncelleme yapıldı' ile başlayan yorumunun ekranda görünür kaldığını test et."""
        comment = TicketComment.objects.create(
            ticket=self.ticket_tech,
            author=self.normal_user,
            content="Güncelleme yapıldı, kontrolleri sağlayabilirsiniz."
        )
        self.client.login(username='superadmin', password='AdminPass123!')
        url = reverse('ticket_detail', kwargs={'pk': self.ticket_tech.pk})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Güncelleme yapıldı, kontrolleri sağlayabilirsiniz.")

    # 13. EKSİK KALAN MANTIKSAL ÖZELLİKLER (3.1 - 3.5) TESTLERİ
    def test_customer_comment_notifies_assigned_agent(self):
        """Müşteri yanıt verdiğinde talebe atanmış yetkiliye bildirim gittiğini test et (3.1)."""
        # Talebi tech_user'a ata
        self.ticket_tech.assigned_to = self.tech_user
        self.ticket_tech.save(update_fields=['assigned_to'])

        # Müşteri (john_doe) giriş yapıp yorum göndersin
        self.client.login(username='john_doe', password='UserPass123!')
        url = reverse('ticket_detail', kwargs={'pk': self.ticket_tech.pk})
        res = self.client.post(url, {'content': 'Sorunum hala devam ediyor, kontrol edebilir misiniz?'})
        self.assertEqual(res.status_code, 302)

        # tech_user için bildirim oluştuğunu doğrula
        notif = Notification.objects.filter(recipient=self.tech_user, ticket=self.ticket_tech).first()
        self.assertIsNotNone(notif)
        self.assertIn("Sorumlu olduğunuz", notif.message)
        self.assertEqual(notif.actor, self.normal_user)

    def test_ticket_assignment_notification_on_edit_and_bulk(self):
        """Talebin yeni bir personele atanmasında o personele bildirim gittiğini test et (3.2)."""
        # 1. ticket_edit ile atama
        self.client.login(username='superadmin', password='AdminPass123!')
        edit_url = reverse('ticket_edit', kwargs={'pk': self.ticket_fin.pk})
        res = self.client.post(edit_url, {
            'title': self.ticket_fin.title,
            'description': self.ticket_fin.description,
            'priority': self.ticket_fin.priority,
            'status': self.ticket_fin.status,
            'category': self.cat_fin.id,
            'assigned_to': self.fin_user.id
        })
        self.assertEqual(res.status_code, 302)
        notif_single = Notification.objects.filter(recipient=self.fin_user, ticket=self.ticket_fin).first()
        self.assertIsNotNone(notif_single)
        self.assertIn("talebi size atandı", notif_single.message)

        # 2. bulk_ticket_action ile atama
        bulk_url = reverse('bulk_ticket_action')
        res_bulk = self.client.post(bulk_url, {
            'bulk_action': 'assign',
            'bulk_target_value': str(self.tech_user.id),
            'selected_tickets': [self.ticket_fin.id]
        })
        self.assertEqual(res_bulk.status_code, 302)
        notif_bulk = Notification.objects.filter(recipient=self.tech_user, ticket=self.ticket_fin).first()
        self.assertIsNotNone(notif_bulk)
        self.assertIn("talebi size atandı", notif_bulk.message)

    def test_user_profile_first_and_last_name_update(self):
        """Kullanıcı profilinde Ad ve Soyad alanlarının güncellenebildiğini test et (3.3)."""
        self.client.login(username='john_doe', password='UserPass123!')
        profile_url = reverse('profile')
        post_data = {
            'first_name': 'Ahmet',
            'last_name': 'Yılmaz',
            'username': 'john_doe',
            'email': 'john@example.com',
            'current_password': 'UserPass123!'
        }
        res = self.client.post(profile_url, post_data)
        self.assertEqual(res.status_code, 302)
        self.normal_user.refresh_from_db()
        self.assertEqual(self.normal_user.first_name, 'Ahmet')
        self.assertEqual(self.normal_user.last_name, 'Yılmaz')
        self.assertEqual(self.normal_user.get_full_name(), 'Ahmet Yılmaz')

    # 14. AŞAMA 4 TESTLERİ (4.1 & 4.2)
    def test_totp_generation_and_2fa_login_flow(self):
        """2FA TOTP üretimi, doğrulaması ve giriş güvenlik akışını test et (4.2.1)."""
        secret = generate_totp_secret()
        self.assertEqual(len(secret), 32)
        valid_code = get_totp_token(secret)
        self.assertTrue(verify_totp_token(secret, valid_code))
        self.assertFalse(verify_totp_token(secret, "000000" if valid_code != "000000" else "111111"))

        # Kullanıcıda 2FA'yı aktifleştir
        self.tech_user.profile.totp_secret = secret
        self.tech_user.profile.is_2fa_enabled = True
        self.tech_user.profile.save()

        # Giriş yapmayı dene -> 2FA ara sayfasına yönlenmeli
        login_url = reverse('login')
        res_login = self.client.post(login_url, {'username': 'tech_agent', 'password': 'TechPass123!'})
        self.assertEqual(res_login.status_code, 302)
        self.assertIn(reverse('verify_2fa'), res_login.url)

        # Hatalı 2FA kodu gir
        verify_url = reverse('verify_2fa')
        res_fail = self.client.post(verify_url, {'token': '999999'})
        self.assertEqual(res_fail.status_code, 200)

        # Doğru 2FA kodu gir
        current_token = get_totp_token(secret)
        res_success = self.client.post(verify_url, {'token': current_token})
        self.assertEqual(res_success.status_code, 302)

    def test_magic_bytes_file_validation(self):
        """Magic bytes denetimi ile sahte uzantılı dosyaların engellendiğini test et (4.2.2)."""
        # 1. Gerçek PDF başlığı -> Geçmeli
        valid_pdf = SimpleUploadedFile("belge.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", content_type="application/pdf")
        validate_file_security(valid_pdf)

        # 2. Sahte PDF (Metin/HTML içeren sahte PDF) -> ValidationError fırlatmalı
        fake_pdf = SimpleUploadedFile("sahte.pdf", b"<html><body>Not a PDF</body></html>", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_file_security(fake_pdf)

        # 3. Sahte Görsel (PNG uzantılı PHP scripti) -> ValidationError fırlatmalı
        fake_png = SimpleUploadedFile("zararli.png", b"<?php echo 'malware'; ?>", content_type="image/png")
        with self.assertRaises(ValidationError):
            validate_file_security(fake_png)

        # 4. Sahte ZIP arşivi -> ValidationError fırlatmalı
        fake_zip = SimpleUploadedFile("arsiv.zip", b"Bu bir zip degildir.", content_type="application/zip")
        with self.assertRaises(ValidationError):
            validate_file_security(fake_zip)

    def test_canned_responses_api_and_permissions(self):
        """Hazır yanıt şablonlarının API üzerinden yetkili personellere sunulduğunu test et (4.1.3)."""
        canned = CannedResponse.objects.create(
            title="Standart Karşılama",
            content="Merhaba, talebiniz tarafımıza ulaşmıştır.",
            category=self.cat_tech,
            created_by=self.super_user
        )

        api_url = reverse('canned_responses_api')

        # Yetkisiz (standart kullanıcı) erişimi -> 403 Forbidden
        self.client.login(username='john_doe', password='UserPass123!')
        res_forbidden = self.client.get(api_url)
        self.assertEqual(res_forbidden.status_code, 403)

        # Yetkili personel erişimi -> 200 OK ve şablon listesi
        self.client.login(username='tech_agent', password='TechPass123!')
        res_ok = self.client.get(api_url)
        self.assertEqual(res_ok.status_code, 200)
        json_data = res_ok.json()
        self.assertEqual(json_data['status'], 'success')
        self.assertTrue(any(item['title'] == "Standart Karşılama" for item in json_data['canned_responses']))

    def test_inbound_email_webhook_integration(self):
        """E-posta üzerinden yanıtlama (Inbound Email Parsing) webhook akışını test et (4.1.4)."""
        webhook_url = reverse('inbound_email_webhook')
        secret = getattr(settings, 'INBOUND_EMAIL_WEBHOOK_SECRET', settings.SECRET_KEY[:32])

        # 1. Yetkisiz istek (Secret yok) -> 403
        res_unauthorized = self.client.post(webhook_url, {'subject': 'Re: Test'}, content_type='application/json')
        self.assertEqual(res_unauthorized.status_code, 403)

        # 2. Geçerli e-posta yanıtı
        email_payload = {
            'from': 'john_doe <john@example.com>',
            'subject': f'Re: [Destek Talebi] #{self.ticket_tech.ticket_number} Talebinize Yeni Yanıt Geldi',
            'text': 'Yazıcının güç kablosunu kontrol ettim ancak ışığı yanmıyor.\n\n> Eski mail alıntısı:\n> Talebiniz inceleniyor...'
        }
        res_success = self.client.post(
            f"{webhook_url}?token={secret}",
            email_payload,
            content_type='application/json'
        )
        self.assertEqual(res_success.status_code, 200)
        resp_json = res_success.json()
        self.assertEqual(resp_json['status'], 'success')

        # Veritabanında yorum oluştu mu kontrol et
        new_comment = TicketComment.objects.filter(id=resp_json['comment_id']).first()
        self.assertIsNotNone(new_comment)
        self.assertEqual(new_comment.author, self.normal_user)
        self.assertIn("güç kablosunu kontrol ettim", new_comment.content)
        self.assertNotIn("Eski mail alıntısı", new_comment.content)

    # 4. AŞAMA 4 TESTLERİ (PDF DIŞA AKTARMA, AI COPILOT & WEBHOOK)
    def test_export_ticket_pdf(self):
        """Talep PDF çıktısının oluşturulmasını ve yetki kontrollerini test et (4.3)."""
        pdf_url = reverse('export_ticket_pdf', kwargs={'pk': self.ticket_tech.pk})

        # 1. Giriş yapmamış kullanıcı -> Login sayfasına yönlendirme (302)
        res_anon = self.client.get(pdf_url)
        self.assertEqual(res_anon.status_code, 302)

        # 2. Yetkisiz başka bir standart kullanıcı -> 403 Forbidden
        other_user = User.objects.create_user('jane_doe', 'jane@example.com', 'JanePass123!')
        self.client.login(username='jane_doe', password='JanePass123!')
        res_forbidden = self.client.get(pdf_url)
        self.assertEqual(res_forbidden.status_code, 403)

        # 3. Talebin sahibi (normal_user) -> 200 OK & application/pdf
        self.client.login(username='john_doe', password='UserPass123!')
        res_owner = self.client.get(pdf_url)
        self.assertEqual(res_owner.status_code, 200)
        pdf_bytes = b"".join(res_owner.streaming_content)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

        # 4. Yetkili teknik destek personeli -> 200 OK & application/pdf
        self.client.login(username='tech_agent', password='TechPass123!')
        res_agent = self.client.get(pdf_url)
        self.assertEqual(res_agent.status_code, 200)
        self.assertEqual(res_agent['Content-Type'], 'application/pdf')

        # 5. Quill zengin metin içeren karmaşık HTML açıklamalı talep PDF üretimi
        rich_ticket = Ticket.objects.create(
            title='Zengin Metinli Talep <script> & test',
            description='<p><strong>M<em>erhaba <u>nas\u0131ls\u0131n </u></em></strong></p><ol><li data-list="ordered"><span class="ql-ui" contenteditable="false"></span>evet</li><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>bilemeyiz</li></ol><blockquote>ne derler?</blockquote><div class="ql-code-block-container"><div class="ql-code-block">python manage.py runserver</div></div><p>evet</p>',
            category=self.cat_tech,
            created_by=self.normal_user,
            is_public=False
        )
        TicketComment.objects.create(
            ticket=rich_ticket,
            author=self.tech_user,
            content='<p>Yanıt: <b>Çözüldü</b> &amp; onaylandı!</p>',
            is_solution=True
        )
        res_rich = self.client.get(reverse('export_ticket_pdf', kwargs={'pk': rich_ticket.pk}))
        self.assertEqual(res_rich.status_code, 200)
        rich_pdf_bytes = b"".join(res_rich.streaming_content)
        self.assertTrue(len(rich_pdf_bytes) > 1000)
        self.assertTrue(rich_pdf_bytes.startswith(b'%PDF'))

    def test_ai_suggest_meta_api(self):
        """AI Copilot canlı kategori ve öncelik öneri API'sini test et (4.4)."""
        api_url = reverse('ai_suggest_meta_api')

        # 1. Giriş yapmamış kullanıcı -> 302 Redirect
        res_anon = self.client.get(api_url)
        self.assertEqual(res_anon.status_code, 302)

        self.client.login(username='john_doe', password='UserPass123!')

        # 2. Yetersiz metin -> idle
        res_idle = self.client.get(f"{api_url}?title=ab&description=cd")
        self.assertEqual(res_idle.status_code, 200)
        self.assertEqual(res_idle.json()['status'], 'idle')

        # 3. Kritik fatura ödeme hatası metni -> Urgent & Finans tahmini
        res_urgent = self.client.get(
            f"{api_url}?title=Acil Fatura Sorunu&description=Kredi kartımdan ödeme çekildi fakat sistem çöktü fatura dekontu çıkmadı"
        )
        self.assertEqual(res_urgent.status_code, 200)
        data = res_urgent.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['suggested_priority'], 'urgent')
        self.assertEqual(data['suggested_category_name'], 'Finans')

    def test_ai_summarize_ticket_api(self):
        """AI Copilot tek cümlelik yönetici özeti API'sini test et (4.4)."""
        summary_url = reverse('ai_summarize_ticket_api', kwargs={'pk': self.ticket_tech.pk})

        # 1. Standart kullanıcı -> 403 Forbidden
        self.client.login(username='john_doe', password='UserPass123!')
        res_user = self.client.get(summary_url)
        self.assertEqual(res_user.status_code, 403)

        # 2. Yetkili personel -> 200 OK ve özet metni
        self.client.login(username='tech_agent', password='TechPass123!')
        res_staff = self.client.get(summary_url)
        self.assertEqual(res_staff.status_code, 200)
        data = res_staff.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn("john_doe", data['summary'])
        self.assertIn("Yazıcı Arızası", data['summary'])

    def test_outgoing_webhook_dispatcher(self):
        """Acil durum dışa giden webhook tetikleyicisinin hatasız çalıştığını test et (4.2)."""
        from tickets.webhooks import send_outgoing_webhook
        try:
            send_outgoing_webhook(self.ticket_tech, event_type="urgent_ticket_created")
        except Exception as e:
            self.fail(f"send_outgoing_webhook beklenmeyen hata fırlattı: {e}")

    def test_logout_user(self):
        """Kullanıcının başarıyla çıkış yapıp login sayfasına yönlendirildiğini test et."""
        self.client.login(username='john_doe', password='UserPass123!')
        res = self.client.get(reverse('logout'))
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, reverse('login'))
        # Tekrar korumalı bir sayfaya erişmeye çalıştığında login'e yönlenmeli
        res_profile = self.client.get(reverse('profile'))
        self.assertEqual(res_profile.status_code, 302)

    # 5. GÜVENLİK VE VERİ BÜTÜNLÜĞÜ İYİLEŞTİRMELERİ TESTLERİ (1.1 - 1.5)
    def test_user_delete_protects_tickets(self):
        """Kullanıcı silinmeye çalışıldığında biletlerin CASCADE ile yok olmasını önleyen PROTECT kuralını doğrula (1.1)."""
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.normal_user.delete()

    def test_ticket_post_delete_cleans_attachment(self):
        """Talep veya yorum silindiğinde ekteki dosyanın diskten/depodan silindiğini doğrula (1.2)."""
        from django.core.files.storage import default_storage
        sample_file = SimpleUploadedFile("delete_test.png", b"fake_png_data", content_type="image/png")
        temp_ticket = Ticket.objects.create(
            title="Dosya Silme Testi",
            description="Açıklama",
            created_by=self.normal_user,
            attachment=sample_file
        )
        file_name = temp_ticket.attachment.name
        self.assertTrue(default_storage.exists(file_name))

        # Talebi sil -> Sinyal dosyayı depodan temizlemeli
        temp_ticket.delete()
        self.assertFalse(default_storage.exists(file_name))

    def test_session_security_settings(self):
        """Oturum zaman aşımı ve HTTPOnly güvenlik başlıklarını doğrula (1.5)."""
        self.assertEqual(getattr(settings, 'SESSION_COOKIE_AGE', None), 28800)
        self.assertTrue(getattr(settings, 'SESSION_COOKIE_HTTPONLY', False))
        self.assertTrue(getattr(settings, 'SESSION_EXPIRE_AT_BROWSER_CLOSE', False))





