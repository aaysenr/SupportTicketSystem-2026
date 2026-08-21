# 🎧 Destek Talep Yönetim Sistemi (Support Ticket System)

Modern, güvenli ve kullanıcı dostu bir **Django** tabanlı Destek Talep (Ticket) Yönetim Uygulaması. Kullanıcıların destek talepleri açabildiği, taleplere yorum yazabildiği, durumlarını takip edebildiği ve yöneticilerin tüm talepleri canlı dashboard üzerinden yönetebildiği tam teşekküllü bir web uygulamasıdır.

---

## 🌟 Öne Çıkan Özellikler

- **🔐 Kullanıcı Kimlik Doğrulama & Oturum Yönetimi:**
  - Kullanıcı Kaydı (`Register`), Giriş (`Login`) ve Çıkış (`Logout`).
  - `@login_required` decorator'ı ile korunan güvenli sayfalar.
- **🛡️ Kullanıcı Bazlı Veri Gizliliği (Data Privacy):**
  - Standart kullanıcılar **sadece kendi açtıkları** destek taleplerini görebilir, düzenleyebilir ve silebilir.
  - Yöneticiler (`is_staff`) sistemdeki tüm talepleri ve istatistikleri görebilir.
  - Adres çubuğundan ID değiştirilerek yapılan yetkisiz erişimlere (IDOR) karşı güvenlik kontrolü.
- **📊 Canlı İstatistik Dashboard Paneli:**
  - Sayfanın üst kısmında *Toplam Talep*, *Açık Talepler*, *Çözülen Talepler* ve *Acil Talepler* için anlık veri sayaçları (`.count()`).
- **🔍 Dinamik Arama ve Filtreleme Mimarisi:**
  - Django ORM `Q` nesneleri ile kelime bazlı (Başlık ve Açıklamada) arama.
  - Durum (*Açık, Devam Ediyor, Çözüldü, Kapalı*) ve Öncelik (*Düşük, Orta, Yüksek, Acil*) filtreleri.
- **💬 Yorum ve Takip Sistemi:**
  - Taleplerin altında kronolojik sıralı yorum geçmişi.
  - Her talep için durum (Status) güncelleme ve detay takibi.
- **⚙️ Django Admin Paneli Entegrasyonu:**
  - Özelleştirilmiş filtreler, arama çubukları ve listeleme kurallarıyla admin yönetimi.

---

## 🛠️ Kullanılan Teknolojiler

- **Backend Framework:** Python 3.x, Django 5.x / 6.x
- **Frontend / UI:** HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons
- **Veritabanı:** SQLite3 (Django ORM)
- **Versiyon Kontrol:** Git & GitHub

---

## 🚀 Proje Kurulum Rehberi

Projeyi yerel bilgisayarınızda çalıştırmak için aşağıdaki adımları sırasıyla takip edebilirsiniz:

### 1. Repoyu Klonlayın veya Klasöre Gidin
```bash
git clone https://github.com/kullanici-adi/support-ticket-system.git
cd "Support Ticket System"
