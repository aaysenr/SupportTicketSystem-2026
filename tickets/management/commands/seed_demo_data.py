import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from tickets.models import (
    Category, TicketTag, Ticket, TicketComment,
    TicketActivityLog, Notification, ChatGroup, ChatMessage,
    UserProfile, KnowledgeBaseArticle, TicketRating, CannedResponse
)


class Command(BaseCommand):
    help = "Staj sunumu ve teslimi için veritabanını temizler, profesyonel demo kullanıcıları ve gerçekçi talep verileri oluşturur."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean-media',
            action='store_true',
            default=True,
            help='Eski test eklerini ve geçici dosyaları diskten temizler.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(self.style.SUCCESS("  DESTEK TALEP SİSTEMİ - STAJ TESLİM VERİLERİ KURULUMU"))
        self.stdout.write(self.style.SUCCESS("=" * 65))

        # 1. Medya ve Log Temizliği
        if options.get('clean_media'):
            media_root = Path(settings.MEDIA_ROOT)
            if media_root.exists():
                for sub in ['ticket_attachments', 'comment_attachments']:
                    sub_path = media_root / sub
                    if sub_path.exists():
                        shutil.rmtree(sub_path, ignore_errors=True)
                        sub_path.mkdir(parents=True, exist_ok=True)
                self.stdout.write(self.style.SUCCESS("• Medya klasöründeki eski test ekleri temizlendi."))

            logs_file = Path(settings.BASE_DIR) / "logs" / "django_errors.log"
            if logs_file.exists():
                logs_file.write_text("", encoding="utf-8")
                self.stdout.write(self.style.SUCCESS("• Test hata günlükleri (django_errors.log) sıfırlandı."))

        # 2. Eski Test Kullanıcılarını ve Verileri Temizle
        Ticket.objects.all().delete()
        TicketComment.objects.all().delete()
        Notification.objects.all().delete()
        TicketActivityLog.objects.all().delete()
        ChatMessage.objects.all().delete()
        ChatGroup.objects.all().delete()
        TicketRating.objects.all().delete()
        KnowledgeBaseArticle.objects.all().delete()
        CannedResponse.objects.all().delete()

        # Rastgele test kullanıcılarını sil
        User.objects.filter(username__in=[
            'new_user', 'new_user0', 'user3', 'user4', 'user77', 'user8', 'sevim00'
        ]).delete()

        # 3. Profesyonel Kategorileri Hazırla
        cat_yazilim, _ = Category.objects.get_or_create(
            name='Yazılım & Uygulama Hataları',
            defaults={'description': 'Şirket içi ERP, web uygulamaları ve yazılım lisans sorunları.'}
        )
        cat_donanim, _ = Category.objects.get_or_create(
            name='Donanım & Ekipman',
            defaults={'description': 'Bilgisayar, monitör, yazıcı ve donanım arızaları.'}
        )
        cat_ag, _ = Category.objects.get_or_create(
            name='Ağ & İnternet Sorunları',
            defaults={'description': 'VPN, WiFi, internet erişimi ve yerel ağ problemleri.'}
        )
        cat_finans, _ = Category.objects.get_or_create(
            name='Ödeme & Faturalandırma',
            defaults={'description': 'E-fatura, ödeme dekontları ve finansal destek talepleri.'}
        )
        cat_ik, _ = Category.objects.get_or_create(
            name='İnsan Kaynakları & İdari',
            defaults={'description': 'İzin, kartlı geçiş ve idari işler bildirimleri.'}
        )

        # 4. Etiketler (Tags)
        tag_yazilim, _ = TicketTag.objects.get_or_create(name='yazılım', defaults={'color': '#2563eb'})
        tag_donanim, _ = TicketTag.objects.get_or_create(name='donanım', defaults={'color': '#dc2626'})
        tag_acil, _ = TicketTag.objects.get_or_create(name='acil', defaults={'color': '#ef4444'})
        tag_vpn, _ = TicketTag.objects.get_or_create(name='vpn', defaults={'color': '#16a34a'})
        tag_fatura, _ = TicketTag.objects.get_or_create(name='fatura', defaults={'color': '#d97706'})
        tag_lisans, _ = TicketTag.objects.get_or_create(name='lisans', defaults={'color': '#9333ea'})

        # 5. Standart ve Anlaşılır Kullanıcı Hesapları
        # A) Süper Yönetici (Admin)
        admin_user, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@desteksistemi.com'})
        admin_user.set_password('Admin123!')
        admin_user.first_name = 'Sistem'
        admin_user.last_name = 'Yöneticisi'
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.save()
        admin_prof, _ = UserProfile.objects.get_or_create(user=admin_user)
        admin_prof.role = 'superadmin'
        admin_prof.save()

        # B) Teknik Destek Uzmanı (Staff)
        tech_user, _ = User.objects.get_or_create(username='destek_uzmani', defaults={'email': 'destek@desteksistemi.com'})
        tech_user.set_password('Destek123!')
        tech_user.first_name = 'Can'
        tech_user.last_name = 'Öztürk'
        tech_user.is_staff = True
        tech_user.is_active = True
        tech_user.save()
        tech_prof, _ = UserProfile.objects.get_or_create(user=tech_user)
        tech_prof.role = 'support_agent'
        tech_prof.assigned_categories.set([cat_yazilim, cat_donanim, cat_ag])
        tech_prof.save()

        # C) Finans Destek Uzmanı (Staff)
        fin_user, _ = User.objects.get_or_create(username='finans_uzmani', defaults={'email': 'finans@desteksistemi.com'})
        fin_user.set_password('Finans123!')
        fin_user.first_name = 'Selin'
        fin_user.last_name = 'Kaya'
        fin_user.is_staff = True
        fin_user.is_active = True
        fin_user.save()
        fin_prof, _ = UserProfile.objects.get_or_create(user=fin_user)
        fin_prof.role = 'finance_agent'
        fin_prof.assigned_categories.set([cat_finans])
        fin_prof.save()

        # D) Standart Müşteriler / Personel
        user1, _ = User.objects.get_or_create(username='ahmet_yilmaz', defaults={'email': 'ahmet@sirket.com'})
        user1.set_password('User123!')
        user1.first_name = 'Ahmet'
        user1.last_name = 'Yılmaz'
        user1.is_staff = False
        user1.is_active = True
        user1.save()

        user2, _ = User.objects.get_or_create(username='ayse_demir', defaults={'email': 'ayse@sirket.com'})
        user2.set_password('User123!')
        user2.first_name = 'Ayşe'
        user2.last_name = 'Demir'
        user2.is_staff = False
        user2.is_active = True
        user2.save()

        self.stdout.write(self.style.SUCCESS("• Demo kullanıcı hesapları (Admin, Destek Uzmanı, Finans Uzmanı, Müşteri) hazırlandı."))

        # 6. Gerçekçi Demo Destek Talepleri (Farklı Statü ve Önceliklerde)
        now = timezone.now()

        # Talep 1: Açık & Yüksek Öncelikli (Yazılım)
        t1 = Ticket.objects.create(
            title="ERP Muhasebe Modülü Açılışında Lisans Hatası",
            description="Sabah mesai başlangıcında ERP muhasebe modülünü açmaya çalıştığımda 'Hata Kodu: LIC-402 Sunucu lisansı yanıt vermiyor' uyarısı alıyorum. Bordro hesaplama işlemleri aksıyor, desteğinizi rica ederim.",
            category=cat_yazilim,
            priority='high',
            status='open',
            created_by=user1,
            assigned_to=tech_user,
            is_public=False
        )
        t1.tags.add(tag_yazilim, tag_lisans, tag_acil)
        TicketActivityLog.objects.create(
            ticket=t1,
            actor=user1,
            action="Talep 'Ahmet Yılmaz' tarafından oluşturuldu."
        )
        TicketActivityLog.objects.create(
            ticket=t1,
            actor=admin_user,
            action="Talep 'Can Öztürk (Teknik Destek)' personeline atandı."
        )

        # Talep 2: Devam Ediyor & Yorumlaşmalı (Donanım)
        t2 = Ticket.objects.create(
            title="3. Kat Pazarlama Bölümü Ağ Yazıcısı Çıktı Vermiyor",
            description="3. katta bulunan HP LaserJet ağ yazıcısına yazdırma komutu gönderildiğinde kuyrukta bekliyor ve 'Yazıcı Çevrimdışı' uyarısı veriyor. Cihazın IP adresi üzerinden web arayüzüne de ulaşılamıyor.",
            category=cat_donanim,
            priority='medium',
            status='in_progress',
            created_by=user2,
            assigned_to=tech_user,
            first_response_at=now - timezone.timedelta(hours=2),
            is_public=True
        )
        t2.tags.add(tag_donanim)
        TicketComment.objects.create(
            ticket=t2,
            author=tech_user,
            content="Merhaba Ayşe Hanım, yazıcının switch port bağlantısını kontrol ettik ve cihazın IP çakışması yaşadığını tespit ettik. Statik IP rezervasyonunu yeniliyoruz, 15 dakika içinde test edebileceksiniz."
        )
        TicketComment.objects.create(
            ticket=t2,
            author=tech_user,
            content="İç Not: Switch 3 port 14 üzerinden MAC filtrelemesi yapıldı. Ağ ekibiyle teyit edildi.",
            is_internal=True
        )
        TicketActivityLog.objects.create(
            ticket=t2,
            actor=tech_user,
            action="Talep durumu 'Devam Ediyor' olarak güncellendi."
        )

        # Talep 3: Çözüldü & CSAT 5 Yıldız Değerlendirmeli (Finans)
        t3 = Ticket.objects.create(
            title="Eylül Ayı E-Fatura Vergi Kimlik Numarası Düzeltme Talebi",
            description="Firmamıza kesilen Eylül ayı hizmet faturasında VKN alanının son hanesi eksik yazılmıştır. Muhasebe kaydını tamamlayabilmemiz için faturanın iptal edilip güncel VKN ile yeniden düzenlenmesini rica ederiz.",
            category=cat_finans,
            priority='medium',
            status='resolved',
            created_by=user1,
            assigned_to=fin_user,
            first_response_at=now - timezone.timedelta(days=1, hours=3),
            is_public=False
        )
        t3.tags.add(tag_fatura)
        c3 = TicketComment.objects.create(
            ticket=t3,
            author=fin_user,
            content="Merhaba Ahmet Bey, hatalı kesilen fatura e-Fatura portalı üzerinden iptal edilmiş olup doğru VKN bilgisi ile yeni e-Faturanız düzenlenmiştir. Fatura PDF ve XML nüshası sistemde kayıtlı e-posta adresinize iletilmiştir. İyi çalışmalar dileriz.",
            is_solution=True
        )
        TicketRating.objects.create(
            ticket=t3,
            user=user1,
            score=5,
            feedback="Çok hızlı ve profesyonel dönüş yapıldı, faturamız anında düzeltildi. Teşekkürler!"
        )
        TicketActivityLog.objects.create(
            ticket=t3,
            actor=fin_user,
            action="Yorum (#{}) çözüm olarak işaretlendi; talep 'Çözüldü' statüsüne alındı.".format(c3.id)
        )

        # Talep 4: Acil & SLA Aşıldı Senaryosu (Ağ & VPN)
        t4 = Ticket.objects.create(
            title="Uzaktan Çalışma VPN Bağlantı Kimlik Doğrulama Başarısız",
            description="Evden çalışma sürecinde şirket Fortinet VPN ağına bağlanırken 'Authentication failure (RADIUS)' hatası alıyorum. Şifremi doğru girmeme rağmen erişim sağlanamıyor.",
            category=cat_ag,
            priority='urgent',
            status='open',
            created_by=user2,
            assigned_to=tech_user,
            is_public=False
        )
        t4.tags.add(tag_vpn, tag_acil)
        # SLA aşılmış gibi göstermek için deadline'ı geçmiş zamana çek
        t4.sla_deadline = now - timezone.timedelta(hours=3)
        t4.save(update_fields=['sla_deadline'])
        TicketActivityLog.objects.create(
            ticket=t4,
            actor=user2,
            action="Talep 'Ayşe Demir' tarafından acil öncelikle oluşturuldu."
        )

        # Talep 5: Kapalı Talep
        t5 = Ticket.objects.create(
            title="Yeni Başlayan Personel İçin İntranet ve E-Posta Hesabı Açılışı",
            description="Departmanımıza yeni katılan veri analisti personeli için kurumsal e-posta ve analitik portalı yetkilerinin tanımlanmasını rica ederiz.",
            category=cat_ik,
            priority='low',
            status='closed',
            created_by=user1,
            assigned_to=admin_user,
            first_response_at=now - timezone.timedelta(days=3),
            is_public=True
        )
        TicketComment.objects.create(
            ticket=t5,
            author=admin_user,
            content="Tüm hesaplar açılmış ve giriş şifreleri geçici olarak ilgili personelin İK yetkilisine teslim edilmiştir.",
            is_solution=True
        )

        self.stdout.write(self.style.SUCCESS("• Gerçekçi senaryolara sahip 5 adet destek talebi ve yanıtları eklendi."))

        # 7. Bilgi Bankası (SSS) Makaleleri
        KnowledgeBaseArticle.objects.create(
            title="Uzaktan Çalışma (VPN) Kurulumu ve Bağlantı Sorunları Çözümü",
            category=cat_ag,
            content="""1. Şirket VPN İstemcisini resmi portaldan indirin.
2. Sunucu adresi olarak 'vpn.sirketiniz.com' adresini girin.
3. Kullanıcı adınızı ve parolanızı yazdıktan sonra Authenticator uygulamanızdaki 6 haneli TOTP kodunu doğrulayınız.
4. Bağlantı hatası alırsanız bilgisayarınızın saat dilimini ve yerel ağ DNS ayarlarınızı kontrol ediniz.""",
            keywords="vpn, uzaktan çalışma, fortinet, ağ, internet, erişim",
            views_count=42,
            is_published=True
        )

        KnowledgeBaseArticle.objects.create(
            title="Unutulan Hesap Şifresi ve İki Aşamalı Doğrulama (2FA) Sıfırlama",
            category=cat_yazilim,
            content="""Şifrenizi unuttuysanız giriş sayfasında yer alan 'Şifremi Unuttum' bağlantısına tıklayarak kayıtlı kurumsal e-postanızı giriniz. 
Gelen e-postadaki tek kullanımlık bağlantıya tıklayarak yeni şifrenizi belirleyebilirsiniz.
Eğer Authenticator uygulamanızı kaybettiyseniz veya 2FA kodunuz hata veriyorsa şirket bilgi işlem masası ile iletişime geçerek kimlik teyidi sonrası 2FA sıfırlama talebinde bulunabilirsiniz.""",
            keywords="şifre, parola, sıfırlama, 2fa, iki aşamalı doğrulama, authenticator",
            views_count=28,
            is_published=True
        )

        KnowledgeBaseArticle.objects.create(
            title="Şirket İçi E-Fatura ve Muhasebe Süreçleri Kılavuzu",
            category=cat_finans,
            content="""Masraf beyanları ve kurumsal satınalma faturalarının her ayın en geç 25'ine kadar muhasebe departmanına iletilmesi gerekmektedir.
Fatura taleplerinizde Vergi Kimlik Numarası (VKN), fatura numarası ve harcama onay belgesinin PDF formatında eklenmesi zorunludur.""",
            keywords="fatura, muhasebe, finans, vkn, masraf",
            views_count=19,
            is_published=True
        )

        self.stdout.write(self.style.SUCCESS("• Bilgi Bankası (SSS) makaleleri oluşturuldu."))

        # 8. Hazır Yanıt Şablonları (Canned Responses)
        CannedResponse.objects.create(
            title="Ekran Görüntüsü ve Hata Logu Talebi",
            content="Merhaba, yaşamış olduğunuz sorunu daha detaylı inceleyebilmemiz için lütfen hatanın tam ekran görüntüsünü veya ilgili hata log dosyasını bu talebe ek olarak iletiniz.",
            category=cat_yazilim,
            created_by=tech_user
        )
        CannedResponse.objects.create(
            title="İnceleme Başlatıldı Bilgilendirmesi",
            content="Merhaba, ilettiğiniz destek talebi ilgili teknik birimimiz tarafından incelemeye alınmıştır. İnceleme tamamlandığında bu talep üzerinden tarafınıza geri bildirim sağlanacaktır.",
            created_by=tech_user
        )
        CannedResponse.objects.create(
            title="Çözüm ve Tamamlama Onayı",
            content="Merhaba, talep konusu işlem başarıyla tamamlanmış ve gerekli kontroller sağlanmıştır. Sorununuz devam ederse bu mesaja yanıt verebilir veya yeni bir talep oluşturabilirsiniz. İyi çalışmalar dileriz.",
            created_by=tech_user
        )

        self.stdout.write(self.style.SUCCESS("• Hazır yanıt şablonları (Canned Responses) tanımlandı."))

        # 9. Ekip Sohbeti Odaları ve Örnek Mesajlar
        general_group, _ = ChatGroup.objects.get_or_create(
            is_general=True,
            defaults={'name': 'Genel Ekip Odası', 'created_by': admin_user}
        )
        general_group.members.set([admin_user, tech_user, fin_user])

        ChatMessage.objects.create(
            sender=admin_user,
            group=general_group,
            content="Herkese iyi çalışmalar arkadaşlar. Sistem bakımı bu akşam 22:00'da planlanmıştır, acil durum taleplerini lütfen mesai bitimine kadar tamamlayalım."
        )
        ChatMessage.objects.create(
            sender=tech_user,
            group=general_group,
            content="Bilgilendirme için teşekkürler, açık biletlerin kontrollerini sağlıyoruz."
        )

        self.stdout.write(self.style.SUCCESS("• Ekip sohbet odaları ve karşılama mesajları oluşturuldu."))

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 65))
        self.stdout.write(self.style.SUCCESS("  STAJ TESLİM VERİLERİ KURULUMU BAŞARIYLA TAMAMLANDI!"))
        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write("\n* Staj Sorumlusu Icin Giris Hesaplari:")
        self.stdout.write(" 1. Süper Yönetici : admin          / Admin123!")
        self.stdout.write(" 2. Destek Uzmanı  : destek_uzmani  / Destek123!")
        self.stdout.write(" 3. Finans Uzmanı  : finans_uzmani  / Finans123!")
        self.stdout.write(" 4. Müşteri/Kullanıcı: ahmet_yilmaz / User123!")
        self.stdout.write(" 5. Müşteri/Kullanıcı: ayse_demir   / User123!\n")
        self.stdout.write(self.style.SUCCESS("=" * 65 + "\n"))
