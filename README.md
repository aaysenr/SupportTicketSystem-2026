# 🎧 Destek Talep Yönetim Sistemi (Enterprise Support Ticket System)

Modern, yüksek güvenlikli, ölçeklenebilir ve kurumsal düzeyde bir **Django** tabanlı Destek Talep ve Müşteri Hizmetleri Yönetim Platformu. 

Bu sistem; kullanıcıların destek talepleri oluşturabildiği, güvenli dosya ekleri yükleyebildiği, departman bazlı atanmış personeller ile anlık sohbet edebildiği, **WebSocket ile canlı talep içi mesajlaşma**, **2FA (İki Aşamalı Doğrulama)**, **Excel & PDF Raporlama**, **Talep Birleştirme (Merge)**, **Renkli Etiketleme (Tags)**, **Hazır Yanıt Şablonları**, **E-posta Webhook ile yanıtlama**, SLA ve CSAT metriklerinin takip edildiği ve gerçek zamanlı bildirimlerin sunulduğu uçtan uca kurumsal bir çözümdür.

---

## 🌟 Öne Çıkan Özellikler ve Modüller

### 1. 🛡️ Gelişmiş Güvenlik ve Doğrulama Mimarisi
- **İki Aşamalı Doğrulama (2FA - TOTP):** Standart Google Authenticator / Authy ile uyumlu, saf Python RFC 6238 TOTP motoru. Kullanıcılar profillerinden QR kod okutarak 2FA aktifleştirebilir; girişlerde şifre sonrası 6 haneli zaman damgalı doğrulama kodu sorulur.
- **Dosya Güvenliğinde Magic Bytes Denetimi:** Sadece dosya uzantısına güvenmek yerine dosya başlık baytları (Magic Signatures: PDF, PNG, JPG, ZIP vb.) ve Pillow derinlik analizi yapılır; uzantısı değiştirilmiş zararlı çalıştırılabilir kodlar (PHP, EXE vb.) engellenir.
- **Stored & DOM XSS Koruması:** Zengin metin editöründen (Quill) gelen tüm HTML girdileri `nh3` HTML sanitization kütüphanesi ile filtrelenir. JavaScript betikleri, `onload`/`onerror` gibi olay dinleyicileri veritabanına ulaşmadan temizlenir.
- **Korumalı Dosya İndirme & Dizin Aşımı Engeli:** Yüklenen ekler (`attachments`) doğrudan statik URL üzerinden halka açılmaz. Korumalı görünümler üzerinden sadece biletin sahibi, departman yetkilisi veya süper yönetici tarafından indirilebilir.
- **Kriptografik OTP ve E-Posta Doğrulama:** 6 haneli hesap onay kodları `secrets` modülüyle üretilir; 10 dakika geçerlilik ve kaba kuvvet saldırılarına karşı **5 hatalı deneme sınırı** ile korunur.
- **Gizli Yönetim Paneli ve Özel Hata Ara Katmanı:** Django admin paneli `/super-admin/` yolunda izole edilmiştir. `CustomErrorPageMiddleware` sayesinde `DEBUG=True` iken dahi sarı teknik rota listesi ekrana basılmaz; kullanıcı her zaman özel ve güvenli `404.html` sayfasıyla karşılanır.
- **12-Factor Ortam Değişkeni Desteği:** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` ve SMTP bilgileri `python-dotenv` aracılığıyla `.env` dosyasından okunur.

### 2. ⚡ Gerçek Zamanlı İletişim & Canlı Sohbet (WebSocket & Django Channels)
- **Canlı Destek Talebi Mesajlaşması (Live Ticket Chat):** Destek talebinin detay sayfası Channels WebSocket (`TicketConsumer`) ile bağlanmıştır; müşteriler ve destek ekibi sayfayı yenilemeden anlık mesajlaşır.
- **Kullanıcı Yazıyor... (Typing Indicator):** Hem ekip içi sohbette hem de talep detayında karşı taraf yazarken anlık *"Yetkili / Kullanıcı şu anda yanıt yazıyor..."* animasyonu devreye girer.
- **Asenkron Canlı Ekip Sohbeti:** Personeller ve yöneticiler arası grup ve birebir (DM) anlık mesajlaşma.
- **Gizli Personel Notu İzolasyonu:** Yöneticilerin talep içine düştüğü gizli iç notlar yalnızca yetkili personellere yayınlanır, müşteriye kesinlikle sızdırılmaz.
- **Otomatik Yeniden Bağlanma (Auto-Reconnect):** Ağ kesintilerinde veya sekme uyku modundan çıktığında WebSocket bağlantısı sessizce otomatik yenilenir.

### 3. 📊 Raporlama, Dışa Aktarma & Analiz
- **Biçimlendirilmiş Microsoft Excel (.xlsx) Raporları:** `openpyxl` motoruyla kurumsal renkli başlıklar, otomatik sütun genişlikleri ve aktif arama/filtreleme sonuçlarıyla tam uyumlu Excel çıktısı.
- **Resmi PDF Raporlama:** `reportlab` ile kurumsal başlıklı, SLA metriklerini, bilet detaylarını ve yanıt geçmişini içeren resmi A4 PDF indirme desteği (Çapraz platform font desteğiyle).
- **Kullanıcı Memnuniyeti (CSAT) Trend Çizgi Grafiği:** Son 6 ayın memnuniyet ortalamalarını Chart.js eğrisi ile görselleştiren interaktif gösterge paneli.

### 4. 🏷️ Talep Yönetimi, Etiketleme & Birleştirme (Merge)
- **Renkli Talep Etiketleri (Tags):** Taleplere `#donanım`, `#vpn`, `#yazılım-hatası`, `#acil-iade` gibi renkli etiketler atama ve tek tıkla etiket bazlı filtreleme.
- **Toplu ve Tekil Talep Birleştirme (Merge Tickets):** Mükerrer açılan talepleri tek bir ana talep altında birleştirme, ikincil talepleri otomatik kapatma, etiketleri devretme ve denetim izi (`TicketActivityLog`) oluşturma.
- **Toplu İşlemler (Bulk Actions):** Liste ekranından birden çok talebin durumunu, kategorisini veya atanan yöneticisini tek seferde güncelleme.

### 5. 👥 Rol Tabanlı Yetkilendirme (RBAC) & Departman İzolasyonu
- **Süper Yönetici (Superadmin):** Tüm departmanları, kullanıcıları, talepleri, sistem ayarlarını ve toplu işlemleri yönetir.
- **Departman Personeli (Teknik, Finans vb.):** Yalnızca sorumlu olduğu kategorilere (`assigned_categories`) ait talepleri görüntüler ve yanıtlar.
- **Standart Kullanıcı:** Yalnızca kendi açtığı talepleri ve genel topluluk/forum taleplerini görebilir. Çözülen veya kapatılan taleplerin silinmesi engellenir.

### 6. ⏱️ SLA (Hizmet Seviyesi Anlaşması) Takip Motoru
- Öncelik seviyesine göre dinamik mesai saati (09:00 - 18:00) ve ilk yanıt süresi takibi:
  - 🔴 **Acil (Urgent):** 2 Saat
  - 🟠 **Yüksek (High):** 6 Saat
  - 🟡 **Orta (Medium):** 24 Saat
  - 🟢 **Düşük (Low):** 48 Saat
- **Resmi ve Dini Tatil Algoritması:** Hafta sonlarını, Türkiye resmi tatillerini ve 2025-2028 dini bayram takvimini otomatik atlar.
- Gecikme uyarı rozetleri ve veritabanı indeksli `sla_deadline` takibi.

### 7. 🔔 Bildirimler & Harici Entegrasyonlar
- **Sesli Uyarı & Tarayıcı Masaüstü Bildirimleri:** Web Audio API sentezleyici ile harici dosyasız ses çalma ve sekme arka plandayken masaüstü push bildirimleri.
- **Harici Acil Durum Webhook'ları:** Slack (BlockKit), Discord (Rich Embed) ve Teams için asenkron acil talep bildirimleri (`webhooks.py`).
- **Zengin HTML E-Posta Bildirimleri:** Kurumsal şablonlu, talep durum rozetli asenkron bilgilendirme e-postaları.
- **Hazır Yanıt Şablonları (Canned Responses):** Sık kullanılan yanıtların tek tıkla mesaja eklenmesi.
- **E-Posta Üzerinden Yanıtlama (Inbound Email Parsing):** E-posta yanıtlarını doğrudan bilet yorumuna çeviren güvenli webhook.

---

## 🛠️ Teknoloji Yığını

| Katman | Teknoloji / Kütüphane |
| :--- | :--- |
| **Backend Framework** | Python 3.11+, Django 6.1 |
| **Asenkron / WebSocket** | Django Channels 4.x, Daphne 4.x, Channels-Redis |
| **Raporlama & Dosya** | `openpyxl` (Excel), `reportlab` (PDF), `Pillow` (Görsel Denetim) |
| **Güvenlik & Doğrulama** | `nh3` (HTML Sanitizer), `qrcode` (2FA TOTP), `cryptography` |
| **Veritabanı & Ortam** | PostgreSQL / SQLite, `dj-database-url`, `python-dotenv` |
| **Frontend** | HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons, Quill.js, Chart.js |
| **E-Posta & Webhook** | Asenkron Thread Worker, SMTP, Discord/Slack Webhooks |

---

## 📁 Proje Dizin Mimarisi

```text
Support Ticket System/
│
├── config/                     # Django Proje Çekirdek Ayarları
│   ├── asgi.py                 # WebSocket ve Channels yönlendirmeleri
│   ├── settings.py             # 12-Factor .env destekli sistem ayarları
│   ├── urls.py                 # Ana URL haritası ve gizli super-admin
│   └── wsgi.py                 # WSGI dağıtım dosyası
│
├── tickets/                    # Ana Destek Sistemi Uygulaması
│   ├── consumers.py            # WebSocket Tüketicileri (Ekip Sohbeti & Canlı Talep)
│   ├── forms.py                # Güvenlikli & Validasyonlu Django Formları
│   ├── middleware.py           # Özel 404/403 Hata Yakalayıcı ve URL Gizleyici
│   ├── models.py               # Ticket, Comment, Tag, CSAT, SLA, Chat, Profil Modelleri
│   ├── pdf.py                  # Çapraz Platform Kurumsal PDF Rapor Üreticisi
│   ├── copilot.py              # Akıllı Kategori/Öncelik Sezgisel Motoru & Özetleyici
│   ├── webhooks.py             # Slack / Discord Asenkron Acil Durum Webhook İstemcisi
│   ├── routing.py              # WebSocket URL rotaları
│   ├── tests.py                # 58 Kapsamlı Otomasyon & Güvenlik Testi (%100 Başarı)
│   ├── totp.py                 # RFC 6238 TOTP 2FA ve QR Kod Motoru
│   ├── urls.py                 # Uygulama içi rotalar ve API uç noktaları
│   ├── validators.py           # Magic bytes dosya imza ve boyut doğrulayıcıları
│   ├── views.py                # RBAC, Ticket, Auth, 2FA, Excel, Merge ve REST API Görünümleri
│   ├── management/commands/    # Özel CLI komutları (örn: send_test_email)
│   └── templates/              # Jinja2 / Django HTML ve E-posta Şablonları
│       ├── emails/             # Zengin HTML e-posta bildirim şablonları
│       └── tickets/            # ticket_detail, team_chat, dashboard, ticket_list vb.
│
├── templates/                  # Genel Şablonlar (base.html, 404.html, 403.html, 500.html)
├── media/                      # Kullanıcı ekleri ve profil fotoğrafları (korumalı)
├── logs/                       # Otomatik rotasyonlu merkezi hata logları (django_errors.log)
├── .env.example                # Örnek ortam değişkenleri şablonu
├── requirements.txt            # Python bağımlılıkları listesi (sabitlenmiş sürümler)
└── README.md                   # Proje dokümantasyonu
```

---

## 🚀 Hızlı Kurulum ve Başlatma

### 1. Depoyu Klonlayın veya Klasöre Geçin
```bash
git clone https://github.com/kullanici-adi/support-ticket-system.git
cd "Support Ticket System"
```

### 2. Sanal Ortamı Oluşturun ve Aktifleştirin
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Tanımlayın (`.env`)
```bash
copy .env.example .env     # Windows
cp .env.example .env       # Linux / macOS
```

### 5. Veritabanı Migrasyonlarını Uygulayın
```bash
python manage.py migrate
```

### 6. Süper Yönetici (Admin) Hesabı Oluşturun
```bash
python manage.py createsuperuser
```

### 7. Sunucuyu Başlatın
WebSocket desteğiyle çalıştırmak için Daphne veya `runserver` kullanın:
```bash
python manage.py runserver
```
Tarayıcınızdan `http://127.0.0.1:8000/` adresine giderek sistemi kullanmaya başlayabilirsiniz!

---

## 🧪 Test Süiti ve Doğrulama

Sistem; yetkilendirme, güvenlik açıkları, 2FA TOTP akışları, Magic Bytes filtreleri, SLA tatil hesaplamaları, XSS engellemeleri, Excel/PDF dışa aktarma, bilet birleştirme ve WebSocket API'lerini denetleyen **58 kapsamlı birim ve entegrasyon testine** sahiptir:

```bash
python manage.py test tickets.tests
```

Konsol çıktısı:
```text
Creating test database for alias 'default'...
..........................................................
----------------------------------------------------------------------
Ran 58 tests in 140.773s

OK (58/58 - %100 Başarı)
Destroying test database for alias 'default'...
```

---

## 📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına göz atabilirsiniz.
