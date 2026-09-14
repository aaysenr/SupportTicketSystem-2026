# 🎧 Destek Talep Yönetim Sistemi (Enterprise Support Ticket System)

Modern, yüksek güvenlikli, ölçeklenebilir ve kurumsal düzeyde bir **Django** tabanlı Destek Talep ve Müşteri Hizmetleri Yönetim Platformu.

Bu sistem; kullanıcıların destek talepleri oluşturabildiği, güvenli dosya ekleri yükleyebildiği, departman bazlı atanmış personeller ile anlık sohbet edebildiği, **WebSocket ile canlı talep ve ekip mesajlaşması**, **WhatsApp tarzı zaman damgası ve düzenleme/silme kontrolleri**, **2FA (İki Aşamalı Doğrulama)**, **Login Brute-Force Koruması**, **Kurumsal Hesap Silme (Soft-Delete & Anonimleştirme)**, **ACID Veri Bütünlüğü**, **Modüler Views Mimarisi**, **Microsoft Excel (.xlsx) & Resmi PDF Raporlama**, **Talep Birleştirme (Merge)**, **Dinamik Etiketleme (Tags)**, **Hazır Yanıt Şablonları (Canned Responses)**, **E-posta Webhook ile yanıtlama**, **Rol Tabanlı (RBAC) İstatistik Paneli**, **Gelişmiş CSAT Müşteri Değerlendirmeleri Filtreleme/Sıralama**, **SLA Takip Motoru** ve gerçek zamanlı bildirimlerin sunulduğu uçtan uca kurumsal bir çözümdür.

---

## 🎯 Staj Teslimi & Hızlı Başlangıç Rehberi

Bu proje staj teslimi amacıyla hazırlanmış olup, staj sorumlusunun sistemi farklı rollerle (Süper Yönetici, Destek Uzmanı, Finans Uzmanı ve Müşteri) hemen test edebilmesi için gerçekçi verilerle donatılmıştır.

### 🔑 Giriş Hesapları ve Yetkileri

| Kullanıcı Adı | Parola | Rol / Departman | Erişim Yetkisi |
| :--- | :--- | :--- | :--- |
| **`admin`** | `Admin123!` | **Süper Yönetici** | Tüm sisteme, istatistiklere, ayarlara ve tüm taleplere tam yetki |
| **`destek_uzmani`** | `Destek123!` | **Teknik Destek Uzmanı** | Yazılım, Donanım ve Ağ departmanı talepleri, iç notlar & Ekip Sohbeti |
| **`finans_uzmani`** | `Finans123!` | **Finans Destek Uzmanı** | Ödeme & Faturalandırma talepleri, iç notlar & Ekip Sohbeti |
| **`ahmet_yilmaz`** | `User123!` | **Müşteri / Personel** | Talep açma, durum takip etme, yanıtlama ve 5 yıldızlı CSAT değerlendirmesi |
| **`ayse_demir`** | `User123!` | **Müşteri / Personel** | Talep açma, durum takip etme, yanıtlama ve SLA aşım senaryosu |

> 💡 **Demo Verilerini Sıfırlama:**
> Veritabanını dilediğiniz an sıfırlayıp ilk günkü tertemiz haline getirmek için:
> ```bash
> python manage.py seed_demo_data
> ```

---

## 🌟 Öne Çıkan Özellikler ve Modüller

### 1. 🛡️ Gelişmiş Güvenlik, Doğrulama & Hesap Yönetimi Mimarisi
- **İki Aşamalı Doğrulama (2FA - TOTP):** Standart Google Authenticator / Authy ile tam uyumlu, saf Python RFC 6238 TOTP motoru. Kullanıcılar profillerinden QR kod okutarak 2FA aktifleştirebilir; girişlerde şifre sonrası 6 haneli zaman damgalı doğrulama kodu sorulur.
- **Giriş (Login) Brute-Force Koruması:** Standart `/login/` sayfası Django Cache üzerinden istemci IP bazlı hız sınırlamasıyla korunur. Kullanıcıya ilk 4 hatalı denemede kalan hakkı gösterilir; ardışık 5 başarısız denemede IP adresi **10 dakika süreyle kilitlenir**.
- **Kurumsal Hesap Silme (Soft-Delete & KVKK/GDPR Uyumu):**
  - Kullanıcılar ve yöneticiler Profil sayfasındaki *"Tehlikeli Bölge"* üzerinden hesaplarını şifre teyidiyle kapatabilir.
  - **Klasik Veritabanı ve Arşiv Koruması:** Doğrudan hard-delete yapılmaz; açılan ve çözümlenen talepler, yorumlar, CSAT puanları ve SLA denetim kayıtları sistem tutarlılığı için korunur.
  - Kullanıcı bilgileri anonimleştirilir (`deleted_user_<id>`, `deleted_<id>@anonymized.local`, "Silinmiş Kullanıcı"), parolası geçersiz kılınır (`set_unusable_password()`), oturumu kapatılır ve hesabı pasifleştirilir.
  - Silinen personelin açıkta kalan talepleri sahipsiz kalmasın diye otomatik olarak ortak yetkili havuzuna (`assigned_to = None`) aktarılır ve sistem aktivite logu düşülür.
  - **Son Süper Yönetici Koruması:** Sistemde en az bir aktif süper yönetici kalmalıdır; tek kalan süper yönetici hesabını silemez.
- **Otomatik Disk ve Medya Temizliği:** Model sinyalleri (`pre_save` & `post_delete`) ile kullanıcı avatarı değiştirildiğinde veya silindiğinde eski fiziksel dosyalar sunucu diskinden otomatik olarak temizlenir.
- **Şifre Sıfırlama & Konsol Geliştirici Desteği:** `CustomPasswordResetForm` sayesinde şifre sıfırlama bağlantıları hem e-posta ile iletilir hem de geliştirme/test ortamlarında terminale çerçeveli kutu olarak yazdırılarak anında test imkanı sağlar.
- **Dosya Güvenliğinde Magic Bytes Denetimi:** Yalnızca dosya uzantısına güvenmek yerine dosya başlık baytları (Magic Signatures: PDF, PNG, JPG, ZIP vb.) ve Pillow derinlik analizi yapılır; uzantısı değiştirilmiş zararlı çalıştırılabilir kodlar (PHP, EXE vb.) engellenir.
- **Stored & DOM XSS Koruması:** Zengin metin editöründen (Quill) gelen tüm HTML girdileri `nh3` HTML sanitization kütüphanesi ile filtrelenir. JavaScript betikleri, `onload`/`onerror` gibi olay dinleyicileri veritabanına ulaşmadan temizlenir.
- **Korumalı Dosya İndirme & Dizin Aşımı Engeli:** Yüklenen ekler (`attachments`) doğrudan statik URL üzerinden halka açılmaz. Korumalı görünümler üzerinden sadece biletin sahibi, departman yetkilisi veya süper yönetici tarafından indirilebilir.
- **Kriptografik OTP ve E-Posta Doğrulama:** 6 haneli hesap onay kodları `secrets` modülüyle üretilir; 10 dakika geçerlilik ve kaba kuvvet saldırılarına karşı **5 hatalı deneme sınırı** ile korunur.
- **Gizli Yönetim Paneli ve Özel Hata Ara Katmanı:** Django admin paneli `/super-admin/` yolunda izole edilmiştir. `CustomErrorPageMiddleware` sayesinde `DEBUG=True` iken dahi sarı teknik rota listesi ekrana basılmaz; kullanıcı her zaman özel ve kurumsal `404.html`, `403.html` ve `500.html` sayfalarıyla karşılanır.
- **12-Factor Ortam Değişkeni Desteği:** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, Redis ve SMTP bilgileri `python-dotenv` aracılığıyla `.env` dosyasından okunur.

### 2. ⚡ Gerçek Zamanlı İletişim & Ekip Sohbeti (WebSocket & Django Channels)
- **Canlı Destek Talebi Mesajlaşması (Live Ticket Chat):** Destek talebinin detay sayfası Channels WebSocket (`TicketConsumer`) ile bağlanmıştır; müşteriler ve destek ekibi sayfayı yenilemeden anlık mesajlaşır.
- **WhatsApp Tarzı Mesajlaşma & Zaman Damgaları:**
  - Mesaj saatleri (örn: `14:35`) ve düzenlenmiş mesajlarda `(düzenlendi)` etiketi gösterilir.
  - Zaman damgasının üzerine gelindiğinde gönderilme ve son düzenlenme tarih/saat bilgisi detaylı tooltip olarak sunulur.
  - **Seçimli Mesaj Silme:** Kullanıcılar kendi mesajlarını silerken *"Herkesten Sil"* ve *"Benden Sil"* seçeneklerine sahiptir. Başkalarının mesajlarında ise yetkili kullanıcılar mesajı sadece kendi sohbetlerinden kaldırabilir ("Benden Sil").
  - Mesaj düzenleme ve yıldızlama (favorileme) desteği.
- **Kullanıcı Yazıyor... (Typing Indicator):** Hem ekip içi sohbette hem de talep detayında karşı taraf yazarken anlık *"Yetkili / Kullanıcı şu anda yanıt yazıyor..."* animasyonu devreye girer.
- **Gizli Personel Notu İzolasyonu:** Yöneticilerin talep içine düştüğü gizli iç notlar yalnızca yetkili personellere yayınlanır, müşteriye kesinlikle sızdırılmaz.
- **Otomatik Yeniden Bağlanma (Auto-Reconnect):** Ağ kesintilerinde veya sekme uyku modundan çıktığında WebSocket bağlantısı sessizce otomatik yenilenir; WebSocket bağlantısı kurulamadığında adaptif HTTP polling mekanizması yedek olarak çalışır.

### 3. 📊 Rol Tabanlı (RBAC) İstatistik Paneli & Gelişmiş CSAT Analizi
- **Rol Bazlı Gösterge Paneli Ayrımı:**
  - **Süper Yöneticiler (Super Admin):** Tüm sistemdeki talepleri (`Ticket.objects.all()`) kapsayan genel analizleri görür (Kategori Dağılımı, Öncelik Dağılımı, SLA Aşılan Talepler, CSAT Oranı ve 6 Aylık CSAT Trendi).
  - **Departman Yöneticileri (Staff):** Yalnızca sorumlu oldukları departman/kategoriler (`assigned_categories`) veya kendilerine atanmış talepler bazında izole edilmiş istatistikleri görür.
- **Gelişmiş CSAT Müşteri Değerlendirmeleri ve Geri Bildirimler Tablosu (Süper Adminlere Özel):**
  - **Atanan Temsilci Filtresi:** Belirli personele göre veya atanmamış taleplere göre filtreleme.
  - **Talep ID / Numarası Filtresi:** Talep numarasına (`#DES-00010` veya ID) göre doğrudan arama.
  - **Müşteri Kullanıcı No / Adı Filtresi:** Kullanıcı ID (`#id`), kullanıcı adı veya e-postaya göre arama.
  - **Tarih Sıralaması:** En Yeni ve En Eski tarihe göre sıralama.
  - **Duygu Durumu Filtreleri:** Olumlu (4-5 ★), Nötr (3 ★), Olumsuz (1-2 ★) hızlı filtreleri.
  - **Sayfa Konum Kilidi:** Filtreleme yapıldığında sayfa başına atmaz; doğrudan değerlendirmeler kartına odaklanır ve tek tıkla filtreleri temizleme olanağı sunar.
- **Biçimlendirilmiş Microsoft Excel (.xlsx) Raporları:** `openpyxl` motoruyla kurumsal renkli başlıklar, otomatik sütun genişlikleri ve aktif filtreleme sonuçlarıyla tam uyumlu Excel çıktısı.
- **Resmi PDF Raporlama:** `reportlab` ile kurumsal başlıklı, SLA metriklerini, bilet detaylarını ve yanıt geçmişini içeren resmi A4 PDF indirme desteği.

### 4. 🏷️ Talep Yönetimi, Etiketleme & Birleştirme (Merge)
- **Akıllı Etiketleme Sistemi (Tags):**
  - Taleplere renkli etiketler atama ve etiket bazlı filtreleme.
  - Talep oluştururken en çok kullanılan ilk 10 etiketin önerilmesi, kullanıcıların özel etiket tanımlayabilmesi (talep başına en fazla 5 etiket, maks. 20 karakter).
  - Yöneticiler için merkezi etiket düzenleme ve silme API'leri (`edit_tag_api`, `delete_tag_api`).
- **Toplu ve Tekil Talep Birleştirme (Merge Tickets):** Mükerrer açılan talepleri tek bir ana talep altında birleştirme, ikincil talepleri otomatik kapatma, etiketleri devretme ve denetim izi (`TicketActivityLog`) oluşturma.
- **ACID Veri Bütünlüğü (Atomik İşlemler):** Talep birleştirme ve toplu güncelleme işlemleri `@transaction.atomic` ile korunur; kesintilerde yarım kalan veri riski ortadan kaldırılmıştır.
- **Filtre Korumalı Dinamik Sayfalama (Pagination):** Kategori, personel ve etiket filtreleri sayfa değiştirildiğinde korunur.

### 5. ⏱️ SLA (Hizmet Seviyesi Anlaşması) Takip Motoru
- Öncelik seviyesine göre dinamik mesai saati (09:00 - 18:00) ve ilk yanıt süresi takibi:
  - 🔴 **Acil (Urgent):** 2 Saat
  - 🟠 **Yüksek (High):** 6 Saat
  - 🟡 **Orta (Medium):** 24 Saat
  - 🟢 **Düşük (Low):** 48 Saat
- **Resmi ve Dini Tatil Algoritması:** Hafta sonlarını, Türkiye resmi tatillerini ve dini bayram takvimini otomatik atlar.
- Gecikme uyarı rozetleri ve veritabanı indeksli `sla_deadline` takibi.

### 6. 🔔 Bildirim Yönetimi & Harici Entegrasyonlar
- **Gelişmiş Bildirim Kontrolleri:** Tek tek veya toplu bildirim silme (`delete_notification`, `delete_all_notifications`) ve tümünü okundu işaretleme.
- **Sesli Uyarı & Masaüstü Bildirimleri:** Web Audio API sentezleyici ile harici dosyasız ses çalma ve sekme arka plandayken masaüstü push bildirimleri.
- **Harici Acil Durum Webhook'ları:** Slack (BlockKit), Discord (Rich Embed) ve Teams için asenkron acil talep bildirimleri (`webhooks.py`).
- **Zengin HTML E-Posta Bildirimleri:** Kurumsal şablonlu, talep durum rozetli asenkron bilgilendirme e-postaları.
- **Hazır Yanıt Şablonları (Canned Responses):** Sık kullanılan yanıtların tek tıkla mesaja eklenmesi.
- **E-Posta Üzerinden Yanıtlama (Inbound Email Parsing):** E-posta yanıtlarını doğrudan bilet yorumuna çeviren güvenli webhook.
- **Bilgi Bankası (SSS) Entegrasyonu:** Talep oluşturma formu ile Bilgi Bankası arasında çift yönlü hızlı geçiş bağlantıları ve canlı SSS makale önerisi.

---

## 🛠️ Teknoloji Yığını

| Katman | Teknoloji / Kütüphane | Sürüm |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3.11+, Django | 6.1 |
| **Asenkron / WebSocket** | Django Channels, Channels Redis, Daphne, Twisted | 4.3.2 / >=4.2.0 / 4.2.3 |
| **Raporlama & Dosya** | `openpyxl` (Excel), `reportlab` (PDF), `Pillow` | 3.1.5 / 5.0.1 / 12.3.0 |
| **Güvenlik & Doğrulama** | `nh3` (HTML Sanitizer), `qrcode` (2FA TOTP), `cryptography` | 0.3.7 / 8.2 / 50.0.1 |
| **Form Doğrulama & Captcha** | `django-simple-captcha` | 0.7.0 |
| **Veritabanı & Ortam** | PostgreSQL / SQLite, `dj-database-url`, `python-dotenv` | 2.9.13 / 1.2.3 |
| **Frontend** | HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons, Chart.js, Quill.js | Güncel CDN |
| **E-Posta & Webhook** | Asenkron Thread Worker, SMTP, Discord/Slack Webhook | Dahili / Rest |

---

## 📁 Proje Dizin Mimarisi

```text
Support Ticket System/
│
├── config/                     # Django Proje Çekirdek Ayarları
│   ├── asgi.py                 # WebSocket ve Channels yönlendirmeleri (Daphne)
│   ├── settings.py             # 12-Factor .env destekli sistem ayarları & Redis/LocMem Cache
│   ├── urls.py                 # Ana URL haritası ve super-admin rotası
│   └── wsgi.py                 # WSGI üretim dağıtım dosyası
│
├── tickets/                    # Ana Destek Sistemi Uygulaması
│   ├── consumers.py            # WebSocket Tüketicileri (Ekip Sohbeti & Canlı Talep)
│   ├── forms.py                # Güvenlikli Formlar, XSS Temizliği & CustomPasswordResetForm
│   ├── middleware.py           # Özel 404/403/500 Hata Yakalayıcı ve AJAX Koruyucu
│   ├── models.py               # Ticket, Comment, Tag, CSAT, SLA, Chat, Profil Modelleri
│   ├── pdf.py                  # Çapraz Platform Kurumsal Antetli PDF Rapor Üreticisi
│   ├── copilot.py              # Akıllı Kategori/Öncelik Sezgisel Motoru & Özetleyici
│   ├── webhooks.py             # Slack / Discord Asenkron Acil Durum Webhook İstemcisi
│   ├── routing.py              # WebSocket URL rotaları
│   ├── tests.py                # 107 Kapsamlı Otomasyon & Güvenlik Testi (%100 Başarı)
│   ├── totp.py                 # RFC 6238 TOTP 2FA ve QR Kod Motoru
│   ├── urls.py                 # Uygulama içi rotalar ve API uç noktaları
│   ├── validators.py           # Magic bytes dosya imza, boyut ve güvenlik doğrulayıcıları
│   │
│   ├── views/                  # Modüler Görünüm Katmanı (Clean Architecture)
│   │   ├── __init__.py         # Tüm görünümleri dışa aktaran modüler köprü
│   │   ├── common.py           # Asenkron e-posta kuyruğu ve ortak yardımcılar
│   │   ├── auth_views.py       # Login (Brute-Force & Open Redirect korumalı), 2FA, Profil
│   │   ├── ticket_views.py     # Ticket CRUD, Yorumlar, Ekler, Bulk Action & Merge (ACID)
│   │   ├── chat_views.py       # N+1 optimizesi yapılmış Ekip Sohbeti, DM, Arşiv ve API'ler
│   │   ├── dashboard_views.py  # RBAC Yönetici Paneli, Excel/PDF/CSV Raporları
│   │   ├── notification_views.py # Bildirim Listesi, Okundu/Silme İşlemleri (@require_POST)
│   │   ├── kb_views.py         # Bilgi Bankası (SSS) Makaleleri ve Canlı Arama
│   │   ├── api_views.py        # Webhook, CSAT Rating, Hazır Şablonlar, Etiket CRUD
│   │   └── error_views.py      # Özel 404, 403 ve 500 Hata Görünümleri
│   │
│   ├── management/commands/    # CLI Yönetim Komutları
│   │   ├── seed_demo_data.py   # Staj demo verilerini ve hesaplarını otomatik yükleyici
│   │   ├── run_scheduler.py    # Yerleşik SLA ve hesap temizliği arka plan zamanlayıcısı
│   │   ├── check_sla_breaches.py # SLA ihlal denetimi ve webhook tetikleyicisi
│   │   ├── cleanup_unverified_accounts.py # Pasif hesap temizliği
│   │   └── send_test_email.py  # SMTP / Console e-posta test aracı
│   │
│   └── templates/              # Jinja2 / Django HTML ve E-posta Şablonları
│       ├── emails/             # Zengin HTML e-posta bildirim şablonları
│       └── tickets/            # ticket_detail, team_chat, dashboard, ticket_list vb.
│
├── static/                     # Statik Varlıklar (Özel Vektörel SVG Favicon vb.)
├── scripts/                    # Canlı Ortam Otomasyon Betikleri
│   ├── crontab.txt             # Linux/macOS zamanlanmış görev crontab rehberi
│   └── setup_scheduled_tasks.ps1 # Windows Görev Zamanlayıcısı PowerShell betiği
├── templates/                  # Genel Şablonlar (base.html, 404.html, 403.html, 500.html)
├── media/                      # Kullanıcı ekleri ve profil fotoğrafları (yetki korumalı)
├── logs/                       # Otomatik rotasyonlu merkezi log dosyaları
├── .env.example                # Örnek ortam değişkenleri şablonu (PostgreSQL, Redis, SMTP)
├── requirements.txt            # Python bağımlılıkları listesi
└── README.md                   # Güncel proje dokümantasyonu
```

---

## 🚀 Hızlı Kurulum ve Başlatma (Staj Sorumlusu Kılavuzu)

Projeyi kendi bilgisayarınızda (Windows, macOS veya Linux) çalıştırmak için aşağıdaki adımları izleyebilirsiniz:

### 1. Proje Dizinine Geçin
```bash
cd "Support Ticket System"
```

### 2. Sanal Ortamı (Virtualenv) Oluşturun ve Aktifleştirin

* **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
  *(veya CMD: `venv\Scripts\activate.bat`)*

* **Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Gerekli Paketleri Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Veritabanı Tablolarını Oluşturun
```bash
python manage.py migrate
```

### 5. Demo Verilerini ve Test Hesaplarını Yükleyin (Önerilen)
Sistemi sıfırdan hesap açmakla uğraşmadan hemen test edebilmeniz için tek komutla tüm demo ortamını hazırlayabilirsiniz:
```bash
python manage.py seed_demo_data
```
> Bu komut; Süper Yönetici, Destek Uzmanı, Finans Uzmanı ve Müşteri hesaplarını oluşturur; gerçekçi destek taleplerini, bilgi bankası makalelerini ve hazır yanıt şablonlarını otomatik yükler.

### 6. Geliştirme Sunucusunu Başlatın
```bash
python manage.py runserver
```
Tarayıcınızdan **`http://127.0.0.1:8000/`** adresine giderek uygulamayı test etmeye başlayabilirsiniz!

---

## 🧭 Staj Sorumlusu İçin 5 Dakikalık Test Turu

Projeyi test ederken şu akışı izleyerek tüm modülleri deneyimleyebilirsiniz:

1. **Süper Yönetici Girişi:** `admin` / `Admin123!` ile giriş yapın.
   - Üst menüden **"İstatistikler"** sekmesine tıklayarak kategori/öncelik dağılım grafiklerini, SLA ihlallerini ve CSAT memnuniyet analizlerini inceleyin.
   - **"Excel İndir"** ve **"PDF Raporu Al"** butonlarını test edin.
2. **Teknik Destek Uzmanı Girişi:** `destek_uzmani` / `Destek123!` ile giriş yapın.
   - Üst menüden **"Ekip Sohbeti"** sekmesine girerek gerçek zamanlı WebSocket mesajlaşmasını, WhatsApp tarzı mesaj düzenleme/silme ve yıldızlama özelliklerini test edin.
   - Bilet detayında **"⚡ Hazır Yanıt Şablonu"** seçerek mesaja otomatik doldurma yeteneğini inceleyin.
3. **Müşteri / Personel Girişi:** `ahmet_yilmaz` / `User123!` ile giriş yapın.
   - Çözülen e-fatura talebini inceleyin ve sayfa altındaki **5 Yıldızlı Memnuniyet (CSAT)** anketini oylayın.
   - **"Yeni Talep Oluştur"** butonuna basarak başlığa göre canlı Bilgi Bankası (SSS) makalesi öneren yapay zeka sezgisel motorunu test edin.
4. **Arka Plan Görev Otomasyonunu Test Edin:**
   ```bash
   python manage.py run_scheduler --run-once
   ```

---

## 🧪 Test Süiti ve Doğrulama

Sistem; yetkilendirme, RBAC dashboard ayrımı, güvenlik açıkları, 2FA TOTP akışları, Magic Bytes filtreleri, SLA tatil hesaplamaları, XSS engellemeleri, Excel/PDF dışa aktarma, bilet birleştirme, bildirim silme, etiket yönetimi, login brute-force koruması, hesap silme ve WebSocket API'lerini denetleyen **107 kapsamlı otomatik teste** sahiptir:

```bash
python manage.py test
```

Konsol çıktısı:
```text
Creating test database for alias 'default'...
...........................................................................................................
----------------------------------------------------------------------
Ran 107 tests in 221.449s

OK (107/107 - %100 Başarı)
Destroying test database for alias 'default'...
```

---

## 📄 Lisans

Bu proje staj çalışması kapsamında MIT Lisansı altında geliştirilmiştir.
