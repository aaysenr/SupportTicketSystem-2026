# 🎧 Destek Talep Yönetim Sistemi (Enterprise Support Ticket System)

Modern, yüksek güvenlikli, ölçeklenebilir ve kurumsal düzeyde bir **Django** tabanlı Destek Talep ve Müşteri Hizmetleri Yönetim Platformu.

Bu sistem; kullanıcıların destek talepleri oluşturabildiği, güvenli dosya ekleri yükleyebildiği, departman bazlı atanmış personeller ile anlık sohbet edebildiği, **WebSocket ile canlı talep ve ekip mesajlaşması**, **WhatsApp tarzı zaman damgası ve düzenleme/silme kontrolleri**, **2FA (İki Aşamalı Doğrulama)**, **Microsoft Excel (.xlsx) & Resmi PDF Raporlama**, **Talep Birleştirme (Merge)**, **Dinamik Etiketleme (Tags)**, **Hazır Yanıt Şablonları (Canned Responses)**, **E-posta Webhook ile yanıtlama**, **Rol Tabanlı (RBAC) İstatistik Paneli**, **Gelişmiş CSAT Müşteri Değerlendirmeleri Filtreleme/Sıralama**, **SLA Takip Motoru** ve gerçek zamanlı bildirimlerin sunulduğu uçtan uca kurumsal bir çözümdür.

---

## 🌟 Öne Çıkan Özellikler ve Modüller

### 1. 🛡️ Gelişmiş Güvenlik ve Doğrulama Mimarisi
- **İki Aşamalı Doğrulama (2FA - TOTP):** Standart Google Authenticator / Authy ile tam uyumlu, saf Python RFC 6238 TOTP motoru. Kullanıcılar profillerinden QR kod okutarak 2FA aktifleştirebilir; girişlerde şifre sonrası 6 haneli zaman damgalı doğrulama kodu sorulur.
- **Şifre Sıfırlama & Konsol Geliştirici Desteği:** `CustomPasswordResetForm` sayesinde şifre sıfırlama bağlantıları hem e-posta ile iletilir hem de geliştirme/test ortamlarında terminale çerçeveli kutu olarak yazdırılarak anında test imkanı sağlar.
- **Dosya Güvenliğinde Magic Bytes Denetimi:** Yalnızca dosya uzantısına güvenmek yerine dosya başlık baytları (Magic Signatures: PDF, PNG, JPG, ZIP vb.) ve Pillow derinlik analizi yapılır; uzantısı değiştirilmiş zararlı çalıştırılabilir kodlar (PHP, EXE vb.) engellenir.
- **Stored & DOM XSS Koruması:** Zengin metin editöründen (Quill) gelen tüm HTML girdileri `nh3` HTML sanitization kütüphanesi ile filtrelenir. JavaScript betikleri, `onload`/`onerror` gibi olay dinleyicileri veritabanına ulaşmadan temizlenir.
- **Korumalı Dosya İndirme & Dizin Aşımı Engeli:** Yüklenen ekler (`attachments`) doğrudan statik URL üzerinden halka açılmaz. Korumalı görünümler üzerinden sadece biletin sahibi, departman yetkilisi veya süper yönetici tarafından indirilebilir.
- **Kriptografik OTP ve E-Posta Doğrulama:** 6 haneli hesap onay kodları `secrets` modülüyle üretilir; 10 dakika geçerlilik ve kaba kuvvet saldırılarına karşı **5 hatalı deneme sınırı** ile korunur.
- **Gizli Yönetim Paneli ve Özel Hata Ara Katmanı:** Django admin paneli `/super-admin/` yolunda izole edilmiştir. `CustomErrorPageMiddleware` sayesinde `DEBUG=True` iken dahi sarı teknik rota listesi ekrana basılmaz; kullanıcı her zaman özel ve kurumsal `404.html`, `403.html` ve `500.html` sayfalarıyla karşılanır.
- **12-Factor Ortam Değişkeni Desteği:** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` ve SMTP bilgileri `python-dotenv` aracılığıyla `.env` dosyasından okunur.

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
- **Toplu İşlemler (Bulk Actions):** Liste ekranından birden çok talebin durumunu, kategorisini veya atanan yöneticisini tek seferde güncelleme.

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
| **Asenkron / WebSocket** | Django Channels, Daphne, Twisted, Autobahn | 4.3.2 / 4.2.3 |
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
│   ├── asgi.py                 # WebSocket ve Channels yönlendirmeleri
│   ├── settings.py             # 12-Factor .env destekli sistem ayarları
│   ├── urls.py                 # Ana URL haritası ve gizli super-admin
│   └── wsgi.py                 # WSGI dağıtım dosyası
│
├── tickets/                    # Ana Destek Sistemi Uygulaması
│   ├── consumers.py            # WebSocket Tüketicileri (Ekip Sohbeti & Canlı Talep)
│   ├── forms.py                # Güvenlikli Formlar & CustomPasswordResetForm
│   ├── middleware.py           # Özel 404/403/500 Hata Yakalayıcı ve URL Gizleyici
│   ├── models.py               # Ticket, Comment, Tag, CSAT, SLA, Chat, Profil Modelleri
│   ├── pdf.py                  # Çapraz Platform Kurumsal PDF Rapor Üreticisi
│   ├── copilot.py              # Akıllı Kategori/Öncelik Sezgisel Motoru & Özetleyici
│   ├── webhooks.py             # Slack / Discord Asenkron Acil Durum Webhook İstemcisi
│   ├── routing.py              # WebSocket URL rotaları
│   ├── tests.py                # 67 Kapsamlı Otomasyon & Güvenlik Testi (%100 Başarı)
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
├── requirements.txt            # Python bağımlılıkları listesi (kategorize edilmiş)
└── README.md                   # Güncel proje dokümantasyonu
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

Sistem; yetkilendirme, RBAC dashboard ayrımı, güvenlik açıkları, 2FA TOTP akışları, Magic Bytes filtreleri, SLA tatil hesaplamaları, XSS engellemeleri, Excel/PDF dışa aktarma, bilet birleştirme, bildirim silme, etiket yönetimi, konsol şifre sıfırlama çıktısı ve WebSocket API'lerini denetleyen **67 kapsamlı birim ve entegrasyon testine** sahiptir:

```bash
python manage.py test tickets.tests
```

Konsol çıktısı:
```text
Creating test database for alias 'default'...
...................................................................
----------------------------------------------------------------------
Ran 67 tests in 181.274s

OK (67/67 - %100 Başarı)
Destroying test database for alias 'default'...
```

---

## 📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına göz atabilirsiniz.
