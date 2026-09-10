from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.urls import reverse
from tickets.models import Category, Ticket, TicketComment, UserProfile, KnowledgeBaseArticle, TicketRating
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

        # Yanıt verilmemiş ve zaman geçmişse SLA aşılmış olmalı
        urgent_ticket.created_at = timezone.now() - timedelta(hours=3)
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
