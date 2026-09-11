# 🎧 Destek Talep Yönetim Sistemi (Enterprise Support Ticket System)

Modern, yüksek güvenlikli, ölçeklenebilir ve kurumsal düzeyde bir **Django** tabanlı Destek Talep ve Müşteri Hizmetleri Yönetim Platformu. 

Bu sistem; kullanıcıların destek talepleri oluşturabildiği, güvenli dosya ekleri yükleyebildiği, departman bazlı atanmış personeller ile anlık sohbet edebildiği, **WebSocket ile canlı talep içi mesajlaşma**, **2FA (İki Aşamalı Doğrulama)**, **Hazır Yanıt Şablonları**, **E-posta Webhook ile yanıtlama**, SLA ve CSAT metriklerinin takip edildiği ve gerçek zamanlı bildirimlerin sunulduğu uçtan uca kurumsal bir çözümdür.

---

## 🌟 Öne Çıkan Özellikler ve Modüller

### 1. 🛡️ Gelişmiş Güvenlik ve Doğrulama Mimarisi
- **İki Aşamalı Doğrulama (2FA - TOTP):** Standart Google Authenticator / Authy ile uyumlu, saf Python RFC 6238 TOTP motoru. Kullanıcılar profillerinden QR kod okutarak 2FA aktifleştirebilir; girişlerde şifre sonrası 6 haneli zaman damgalı doğrulama kodu sorulur.
- **Dosya Güvenliğinde Magic Bytes Denetimi:** Sadece dosya uzantısına güvenmek yerine dosya başlık baytları (Magic Signatures: PDF, PNG, JPG, ZIP vb.) ve Pillow derinlik analizi yapılır; uzantısı değiştirilmiş zararlı çalıştırılabilir kodlar (PHP, EXE vb.) engellenir.
- **Stored & DOM XSS Koruması:** Zengin metin editöründen (Quill) gelen tüm HTML girdileri `nh3` HTML sanitization kütüphanesi ile filtrelenir. JavaScript betikleri, `onload`/`onerror` gibi olay dinleyicileri veritabanına ulaşmadan temizlenir.
- **Korumalı Dosya İndirme & Dizin Aşımı Engeli:** Yüklenen ekler (`attachments`) doğrudan statik URL üzerinden halka açılmaz. Korumalı görünümler üzerinden sadece biletin sahibi, departman yetkilisi veya süper yönetici tarafından indirilebilir.
- **Kriptografik OTP ve E-Posta Doğrulama:** 6 haneli hesap onay kodları `secrets` modülüyle üretilir; 10 dakika geçerlilik ve kaba kuvvet saldırılarına karşı **5 hatalı deneme sınırı** ile korunur.
- **CSRF Korumalı AJAX Uç Noktaları:** Yorum çözümleme ve beğeni işlemleri yalnızca `POST` metodu ve CSRF belirteçleri ile çalışır.
- **12-Factor Ortam Değişkeni Desteği:** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` ve SMTP bilgileri `python-dotenv` aracılığıyla `.env` dosyasından okunur.

### 2. ⚡ Gerçek Zamanlı İletişim & Canlı Sohbet (WebSocket & Django Channels)
- **Canlı Destek Talebi Mesajlaşması (Live Ticket Chat):** Destek talebinin detay sayfası Channels WebSocket (`TicketCommentConsumer`) ile bağlanmıştır; müşteriler ve destek ekibi sayfayı yenilemeden anlık mesajlaşır.
- **Kullanıcı Yazıyor... (Typing Indicator):** Hem ekip içi sohbette hem de talep detayında karşı taraf yazarken anlık *"Yetkili / Kullanıcı şu anda yanıt yazıyor..."* animasyonu devreye girer.
- **Asenkron Canlı Ekip Sohbeti:** Personeller ve yöneticiler arası grup ve birebir (DM) anlık mesajlaşma.
- **Gizli Personel Notu İzolasyonu:** Yöneticilerin talep içine düştüğü gizli iç notlar yalnızca yetkili personellere yayınlanır, müşteriye kesinlikle sızdırılmaz.

### 3. 📋 Operasyonel Verimlilik & Otomasyon
- **Hazır Yanıt Şablonları (Canned Responses / Quick Replies):** Destek ekibinin sık sorulan sorulara tek tıkla şablon yanıtlar ekleyebilmesini sağlayan şablon yönetim paneli ve dinamik `/api/canned-responses/` API'si.
- **E-Posta Üzerinden Yanıtlama (Inbound Email Parsing):** Müşterilerin destek e-postasına direkt mail programından verdiği yanıtları ayrıştıran, geçmiş alıntıları temizleyen ve otomatik olarak ilgili talebe yorum olarak ekleyen webhook (`/api/inbound-email/`).
- **Asenkron E-posta Altyapısı (Non-Blocking):** `send_notification_email` arka plan iş parçacığı (`threading.Thread`) ile çalışır; form gönderimleri SMTP sunucusunu beklemeden **0 milisaniye gecikmeyle** tamamlanır.

### 4. 👥 Rol Tabanlı Yetkilendirme (RBAC) & Departman İzolasyonu
- **Süper Yönetici (Admin):** Tüm departmanları, kullanıcıları, talepleri, sistem ayarlarını ve toplu işlemleri yönetir.
- **Departman Personeli (Teknik, Finans vb.):** Yalnızca sorumlu olduğu kategorilere (`assigned_categories`) ait talepleri görüntüler ve yanıtlar.
- **Standart Kullanıcı:** Yalnızca kendi açtığı talepleri ve genel bilgi bankasını görebilir. Kendi açık taleplerini silebilir; çözülmüş veya kapatılmış taleplerin silinmesi engellenir.

### 5. ⏱️ SLA (Hizmet Seviyesi Anlaşması) Takip Motoru
- Öncelik seviyesine göre dinamik çalışma saati ve yanıt süresi takibi:
  - 🔴 **Acil (Urgent):** 2 Saat
  - 🟠 **Yüksek (High):** 8 Saat
  - 🟡 **Orta (Medium):** 24 Saat
  - 🟢 **Düşük (Low):** 48 Saat
- Veritabanı seviyesinde indeksli `sla_deadline` alanı ve gecikme uyarı rozetleri.

### 6. ⭐ CSAT (Müşteri Memnuniyeti) ve Bilgi Bankası (KB)
- Çözülen talepler için 1-5 yıldız memnuniyet puanlaması ve geri bildirim formu.
- Departman ve personel bazlı memnuniyet ortalamaları.
- Arama yapılabilir SSS / Bilgi Bankası makaleleri ve atomik (`F()`) sayaç takibi.

### 7. 🌓 Modern UI/UX ve Karanlık Mod (Dark Mode)
- Bootstrap 5.3 tabanlı modern ve responsive tasarım.
- Kalıcı açık/koyu tema geçişi (`localStorage`).
- Quill WYSIWYG zengin metin düzenleyicisi.
- Dinamik filtreleme, sıralama ve CSV dışa aktarma (Export).

---

## 🛠️ Teknoloji Yığını

| Katman | Teknoloji / Kütüphane |
| :--- | :--- |
| **Backend** | Python 3.11+, Django 5.x / 6.x |
| **Asenkron / WebSocket** | Django Channels 4.x, Daphne 4.x, Channels-Redis |
| **Güvenlik & Doğrulama** | `nh3` (HTML Sanitizer), `qrcode` (2FA TOTP), `Pillow` (Magic Bytes) |
| **Ortam & Yapılandırma** | `python-dotenv`, `dj-database-url` |
| **Veritabanı** | SQLite (Yerel / Test), PostgreSQL (Canlı Uyumlu) |
| **Frontend** | HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons, Quill.js |
| **E-Posta Servisi** | Asenkron Thread SMTP (Production) / Console Backend (Geliştirme) |

---

## 📁 Proje Dizin Mimarisi

```text
Support Ticket System/
│
├── config/                     # Django Proje Çekirdek Ayarları
│   ├── asgi.py                 # WebSocket ve Channels yönlendirmeleri
│   ├── settings.py             # 12-Factor .env destekli sistem ayarları
│   ├── urls.py                 # Ana URL yönlendirmeleri
│   └── wsgi.py                 # WSGI dağıtım dosyası
│
├── tickets/                    # Ana Destek Sistemi Paketi
│   ├── consumers.py            # WebSocket Consumers (Ekip Sohbeti & Canlı Talep)
│   ├── forms.py                # XSS Korumalı & Validasyonlu Django Formları
│   ├── models.py               # Ticket, Comment, CannedResponse, CSAT, SLA Modelleri
│   ├── routing.py              # WebSocket URL rotaları
│   ├── tests.py                # 36 Kapsamlı Otomasyon & Güvenlik Testi
│   ├── totp.py                 # RFC 6238 TOTP 2FA ve QR Kod Motoru
│   ├── urls.py                 # Uygulama içi rotalar ve Webhook'lar
│   ├── validators.py           # Magic bytes dosya imza ve boyut doğrulayıcıları
│   ├── views.py                # RBAC, Ticket, Auth, 2FA ve REST API Görünümleri
│   ├── management/commands/    # Özel CLI komutları (örn: send_test_email)
│   ├── static/tickets/         # CSS, JS (tema seçici, sohbet, arama) ve ikonlar
│   └── templates/              # Jinja2 / Django HTML şablonları
│       └── tickets/            # ticket_detail, team_chat, setup_2fa, verify_2fa vb.
│
├── media/                      # Kullanıcı ekleri (korumalı dizin)
├── .env.example                # Örnek ortam değişkenleri şablonu
├── requirements.txt            # Python bağımlılıkları listesi
└── README.md                   # Proje dokümantasyonu
```

---

## 🚀 Hızlı Kurulum ve Başlatma

### 1. Projeyi Klonlayın veya Klasöre Geçin
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

Sistem; yetkilendirme, güvenlik açıkları, 2FA TOTP akışları, Magic Bytes filtreleri, SLA hesaplamaları, XSS engellemeleri ve WebSocket API'lerini denetleyen **36 kapsamlı birim ve entegrasyon testine** sahiptir:

```bash
python manage.py test tickets
```

Konsol çıktısı:
```text
Creating test database for alias 'default'...
....................................
----------------------------------------------------------------------
Ran 36 tests in 106.155s

OK (36/36)
Destroying test database for alias 'default'...
```

---

## 📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına göz atabilirsiniz.
