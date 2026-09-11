# 🎧 Destek Talep Yönetim Sistemi (Enterprise Support Ticket System)

Modern, yüksek güvenlikli, ölçeklenebilir ve kurumsal düzeyde bir **Django** tabanlı Destek Talep ve Müşteri Hizmetleri Yönetim Platformu. 

Bu sistem; kullanıcıların destek talepleri oluşturabildiği, güvenli dosya ekleri yükleyebildiği, departman bazlı atanmış personeller ile anlık sohbet edebildiği, SLA ve CSAT metriklerinin takip edildiği ve gerçek zamanlı bildirimlerin sunulduğu uçtan uca bir çözümdür.

---

## 🌟 Öne Çıkan Özellikler ve Modüller

### 1. 🛡️ Gelişmiş Güvenlik ve Doğrulama Mimarisi
- **Stored & DOM XSS Koruması:** Zengin metin editöründen (Quill) gelen tüm HTML girdileri `nh3` HTML sanitization kütüphanesi ile filtrelenir. JavaScript betikleri, `onload`/`onerror` gibi olay dinleyicileri veritabanına ulaşmadan temizlenir. Frontend tarafında `textContent` güvenli DOM manipülasyonu uygulanır.
- **Korumalı Dosya İndirme & Dizin Aşımı (Directory Traversal) Engeli:** Kullanıcıların yüklediği ekler (`attachments`) doğrudan statik URL üzerinden halka açılmaz. `ticket_attachment_download` ve `comment_attachment_download` korumalı görünümleri üzerinden sadece biletin sahibi, departman yetkilisi veya süper yönetici tarafından indirilebilir.
- **CSRF Korumalı AJAX Uç Noktaları:** Yorum çözümleme (`toggle_comment_solution`) ve beğeni (`toggle_comment_like`) işlemleri yalnızca `POST` metodu ve geçerli CSRF belirteçleri ile çalışır; GET ile tetiklenen CSRF saldırılarına karşı korunur.
- **Kriptografik OTP ve E-Posta Doğrulama:** 6 haneli doğrulama kodları `secrets` modülüyle üretilir. Kodlar 10 dakika süreyle geçerlidir ve kaba kuvvet (brute-force) saldırılarına karşı **5 hatalı deneme sınırı** ile korunur. Süresi dolan veya bloke olan kodlar için "Yeni Kod Gönder" mekanizması mevcuttur.
- **12-Factor Ortam Değişkeni Desteği:** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` ve SMTP kimlik bilgileri `python-dotenv` aracılığıyla `.env` dosyasından dinamik okunur.

### 2. 👥 Rol Tabanlı Yetkilendirme (RBAC) & Departman İzolasyonu
- **Süper Yönetici (Admin):** Tüm departmanları, kullanıcıları, talepleri, sistem ayarlarını ve toplu işlemleri yönetir.
- **Departman Personeli (Agent - Teknik, Finans, İK vb.):** Yalnızca kendi uzmanlık departmanına (`assigned_categories`) ait talepleri görüntüler, durum günceller, dosya indirir ve çözüm sunar. Diğer departmanların verileri izole edilir.
- **Standart Kullanıcı:** Yalnızca kendi açtığı talepleri ve kamuya açık bilgi bankasını görebilir. Kendi açık (`open`, `in_progress`) taleplerini silebilir; çözülmüş veya kapatılmış taleplerin silinmesi veri tutarlılığı için engellenir.

### 3. ⚡ Gerçek Zamanlı İletişim (WebSocket & Django Channels)
- **Asenkron Canlı Ekip Sohbeti:** Daphne ve Channels altyapısıyla grup ve birebir anlık mesajlaşma.
- **Delta Polling Desteği:** REST API (`get_chat_messages_api`) `?after_id=` sorgusu ile yalnızca yeni düşen mesajları çekerek bant genişliğini ve sunucu yükünü minimumda tutar.
- **Canlı Bildirimler:** Yeni yanıtlar ve durum değişiklikleri kullanıcı paneline anlık aktarılır.

### 4. ⏱️ SLA (Hizmet Seviyesi Anlaşması) Takip Motoru
- Öncelik seviyesine göre dinamik yanıt ve çözüm süreleri:
  - 🔴 **Acil (Urgent):** 2 Saat
  - 🟠 **Yüksek (High):** 8 Saat
  - 🟡 **Orta (Medium):** 24 Saat
  - 🟢 **Düşük (Low):** 48 Saat
- Süresi aşılmış talepler arayüzde dinamik uyarı rozetleri (`badge`) ve gecikme sayaçları ile vurgulanır.

### 5. ⭐ CSAT (Müşteri Memnuniyeti) Değerlendirme Sistemi
- Talep çözüldüğünde (`resolved`) kullanıcıya 1-5 yıldız arası puanlama ve yazılı geri bildirim formu sunulur.
- Raporlama panelinde departman ve personel bazlı memnuniyet ortalamaları hesaplanır.

### 6. 📚 Bilgi Bankası (Knowledge Base - KB) & SSS
- Sık karşılaşılan sorunlar için arama yapılabilir makaleler.
- Faydalı bulunan yorumların tek tıkla Bilgi Bankası makalesine dönüştürülmesi.
- Kullanıcıların çözümleri oylayabilmesi ("Faydalı Buldum" butonu).

### 7. 🌓 Modern UI/UX ve Karanlık Mod (Dark Mode)
- Bootstrap 5.3 tabanlı tam duyarlı (responsive) tasarım.
- Tek tıkla açık/koyu tema geçişi (`localStorage` ile kalıcı tema tercihi).
- Quill WYSIWYG zengin metin düzenleyicisi.
- Filtrelenebilir ve sıralanabilir canlı talep tabloları.

---

## 🛠️ Teknoloji Yığını

| Katman | Teknoloji / Kütüphane |
| :--- | :--- |
| **Backend** | Python 3.11+, Django 5.x / 6.x |
| **Asenkron / WebSocket** | Django Channels 4.x, Daphne 4.x |
| **Güvenlik & Filtreleme** | `nh3` (HTML Sanitizer), `python-dotenv`, Django CSRF / Auth |
| **Veritabanı** | SQLite (Geliştirme / Test), PostgreSQL / MySQL (Üretim uyumlu) |
| **Frontend** | HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons, Quill.js |
| **E-Posta Servisi** | SMTP (Production) / Console Backend (Geliştirme & Test) |

---

## 📁 Proje Dizin Mimarisi

```text
Support Ticket System/
│
├── config/                     # Django Proje Çekirdek Ayarları
│   ├── __init__.py
│   ├── asgi.py                 # WebSocket ve Channels yönlendirmeleri
│   ├── settings.py             # 12-Factor .env destekli sistem ayarları
│   ├── urls.py                 # Ana URL yönlendirmeleri
│   └── wsgi.py                 # Standart WSGI dağıtım dosyası
│
├── tickets/                    # Ana Uygulama Paketi
│   ├── consumers.py            # WebSocket Channels Consumer (Ekip Sohbeti)
│   ├── forms.py                # XSS Korumalı & Validasyonlu Django Formları
│   ├── models.py               # Ticket, Comment, CSAT, SLA, Chat & OTP Modelleri
│   ├── tests.py                # 25 Kapsamlı Otomasyon & Güvenlik Testi
│   ├── urls.py                 # Uygulama içi rotalar
│   ├── validators.py           # Dosya türü, uzantı ve boyut doğrulayıcıları
│   ├── views.py                # RBAC, Ticket, Auth ve REST API Görünümleri
│   ├── management/commands/    # Özel CLI komutları (örn: send_test_email)
│   ├── static/tickets/         # CSS, JS (tema seçici, sohbet, arama) ve ikonlar
│   └── templates/              # Jinja2 / Django HTML şablonları
│
├── media/                      # Kullanıcı ekleri (korumalı dizin)
├── .env.example                # Örnek ortam değişkenleri şablonu
├── .gitignore                  # Git dışlama kuralları (.env, media vb.)
├── manage.py                   # Django yönetim aracı
├── requirements.txt            # Python bağımlılıkları listesi
└── README.md                   # Proje dokümantasyonu
```

---

## 🚀 Hızlı Kurulum ve Başlatma

Yerel geliştirme ortamında sistemi ayağa kaldırmak için aşağıdaki adımları uygulayın:

### 1. Projeyi Klonlayın veya Klasöre Geçin
```bash
git clone https://github.com/kullanici-adi/support-ticket-system.git
cd "Support Ticket System"
```

### 2. Sanal Ortamı (Virtualenv) Oluşturun ve Aktifleştirin
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
Proje kök dizininde bulunan `.env.example` dosyasını kopyalayarak `.env` oluşturun:
```bash
copy .env.example .env     # Windows
cp .env.example .env       # Linux / macOS
```

`.env` dosyasını bir metin düzenleyici ile açıp değerleri ayarlayın:
```ini
SECRET_KEY=django-insecure-your-very-secret-and-unique-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# E-posta Ayarları (Geliştirme aşamasında boş bırakılırsa e-postalar konsola yazılır)
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@desteksistemi.com
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
WebSocket desteğinden tam olarak yararlanmak için projeyi Daphne (ASGI) veya `runserver` ile çalıştırabilirsiniz:
```bash
python manage.py runserver
```
Tarayıcınızdan `http://127.0.0.1:8000/` adresine giderek sistemi kullanmaya başlayabilirsiniz!

---

## 🧪 Test Süiti ve Doğrulama

Sistem; yetkilendirme, güvenlik açıkları, SLA hesaplamaları, XSS filtreleri ve WebSocket API'lerini test eden kapsamlı bir test süitine sahiptir:

```bash
python manage.py test
```

Tüm 25 testin başarıyla çalıştığı ve güvenliğin doğrulandığı konsol çıktısı:
```text
Creating test database for alias 'default'...
.........................
----------------------------------------------------------------------
Ran 25 tests in 61.340s

OK
Destroying test database for alias 'default'...
```

### Test Edilen Başlıca Güvenlik Senaryoları:
1. **XSS Sanitization:** HTML içeriklerine enjekte edilmeye çalışılan `<script>` ve `onerror` etiketlerinin `nh3` tarafından engellenmesi.
2. **Korumalı İndirme:** Yetkisiz kullanıcıların başka kullanıcılara ait bilet eklerini indirememesi.
3. **RBAC Ayrıştırması:** Finans yetkilisinin Teknik Destek biletini silememesi; bilet sahibinin kendi açık biletini silebilmesi, kapalı biletini ise silememesi.
4. **CSRF Koruması:** `toggle_comment_solution` ve `toggle_comment_like` uç noktalarına yapılan `GET` çağrılarının `405 Method Not Allowed` ile reddedilmesi.
5. **OTP Güvenliği:** 5 hatalı denemede hesabın geçici kilitlenmesi ve "Yeni Kod Gönder" ile yeni OTP üretilmesi.

---

## 🤝 Katkıda Bulunma

1. Bu depoyu çatallayın (Fork).
2. Yeni özelliğiniz için bir dal oluşturun (`git checkout -b feature/harika-ozellik`).
3. Değişikliklerinizi işleyin (`git commit -m 'feat: Yeni özellik eklendi'`).
4. Dalınıza gönderin (`git push origin feature/harika-ozellik`).
5. Bir Çekme İsteği (Pull Request) açın.

---

## 📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına göz atabilirsiniz.
