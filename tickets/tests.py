from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.urls import reverse
from io import StringIO
from django.core.management import call_command
from django.conf import settings
from tickets.models import Category, Ticket, TicketComment, UserProfile, KnowledgeBaseArticle, TicketRating, Notification, ChatGroup, ChatMessage
from tickets.validators import validate_file_security
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
        """Yorumu çözüm işaretleme ve geri alma durumunu test et."""
        comment = TicketComment.objects.create(ticket=self.ticket_tech, author=self.tech_user, content="Çözüm adımı")
        self.client.login(username='superadmin', password='AdminPass123!')

        # 1. Çözüm olarak işaretle
        url = reverse('toggle_comment_solution', kwargs={'comment_id': comment.id})
        response = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['is_solution'])
        self.assertEqual(data['ticket_status'], 'resolved')

        # 2. Geri Al (Undo): Çözüm işaretini kaldır
        response_undo = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_ACCEPT='application/json')
        self.assertEqual(response_undo.status_code, 200)
        data_undo = response_undo.json()
        self.assertEqual(data_undo['status'], 'ok')
        self.assertFalse(data_undo['is_solution'])
        self.assertEqual(data_undo['ticket_status'], 'in_progress')

    def test_toggle_comment_like_and_undo(self):
        """Yorumu beğenme ve beğeniyi geri alma durumunu test et."""
        comment = TicketComment.objects.create(ticket=self.ticket_tech, author=self.tech_user, content="Faydalı yorum")
        self.client.login(username='john_doe', password='UserPass123!')

        # 1. Beğen (Faydalı bul)
        url = reverse('toggle_comment_like', kwargs={'comment_id': comment.id})
        response = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['liked'])
        self.assertEqual(data['like_count'], 1)

        # 2. Geri Al (Undo): Beğeniyi kaldır
        response_undo = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_ACCEPT='application/json')
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
            category='technical',
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

        # 1. Normal kullanıcı silemez (302 redirect ve hata mesajı)
        self.client.login(username='john_doe', password='UserPass123!')
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


