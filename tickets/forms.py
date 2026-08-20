from django import forms # from django import forms: Django'nun form oluşturma, doğrulama ve widget yönetim modülünü içeri aktarır
from .models import Ticket # Formun hangi veritabanı tablosunu temel alacağını belirtmek için Ticket modelini içe aktarır.

class TicketForm(forms.ModelForm):  # Django'nun hazır ModelForm sınıfından türeyen bir form sınıfı tanımlar. Bu sayede Ticket modelindeki alanları otomatik olarak bir web formuna dönüştürür.
    """
    Ticket modeline dayalı form sınıfı.
    Kullanıcıdan alınacak alanları ve HTML stil (Bootstrap) giydirmelerini yönetir.
    """
    class Meta: # Django'ya bu formun hangi modeli kullanacağını ve hangi alanları göstereceğini bildirir
        model = Ticket # Formun Ticket veritabanı tablosundan türetileceğini belirtir.
        # Formda kullanıcının doldurmasını istediğimiz alanlar:
        fields = ['title', 'category', 'priority', 'description']

        # Form alanlarının HTML görünümünü ve davranışlarını (placeholder, class, rows vb.) tanımlar.
        # ModelForm içindeki Meta sınıfında tanımlanan bu bölüm,
        # formun hangi modelden veri çekeceğini, hangi alanların görünür olacağını
        # ve bu alanların HTML görsel ayarlarını (widgets, labels vb.) belirtir.


        #class Meta: Formun hangi modeli referans alacağını ve hangi kurallarla çalışacağını belirten ayar bloğudur.

        #model = Ticket: Formun bağlanacağı veritabanı modelini seçer.

        #fields = [...]: Kullanıcının formda hangi alanları doldurmasını istediğimizi belirler.

        #Neden created_by, status, created_at yok? Çünkü created_by alanını güvenlik gereği giriş yapan kullanıcıdan (request.user) arka planda otomatik alacağız, 
        # status alanını varsayılan olarak "Açık" başlatacağız ve created_at zaten otomatik tarih atıyor. 
        # Kullanıcının bunları değiştirmesini istemeyiz!
        




        # Form elemanlarına Bootstrap CSS sınıfları ve etiketler ekliyoruz (Widgets)
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Örn: Bilgisayarım açılmıyor / Yazıcı çıktısı alınamıyor'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Yaşadığınız sorunu detaylıca açıklayınız...'
            }),
        }

        #widgets: HTML input etiketlerinin (text, select, textarea vb.) görünümünü ve özelliklerini (class, placeholder vb.) tanımladığımız yerdir.
        #title: TextInput -> <input type="text">
        #category/priority: Select -> <select>
        #description: Textarea -> <textarea>

        #widgets (Görsel Bileşenler / HTML Özelleştirme): Django formları varsayılan olarak düz, biçimsiz HTML etiketleri üretir. widgets sözlüğü sayesinde bu HTML etiketlerine Bootstrap sınıfları ve HTML özellikleri (attrs) giydiririz:

        #title: Tek satırlık metin kutusudur (TextInput). Bootstrap'in modern görünümü için form-control sınıfı ve içine ipucu yazısı (placeholder) eklenir.

        #category & priority: Açılır liste kutusudur (Select - Dropdown). Bootstrap'in şık açılır kutu stili olan form-select sınıfı atanır.

        #description: Çok satırlı metin alanıdır (Textarea). rows: 5 ile kutunun 5 satır yüksekliğinde açılması sağlanır.




        
        labels = {
            'title': 'Talep Başlığı',
            'category': 'Kategori',
            'priority': 'Öncelik Seviyesi',
            'description': 'Detaylı Açıklama',
        }


        #labels: HTML etiketlerinin yanında belirecek olan metinleri (etiketleri) daha anlamlı ve kullanıcı dostu bir şekilde özelleştirmemizi sağlar. 
        #labels (Alan Etiketleri): Form alanlarının üzerinde kullanıcıya görünecek olan Türkçe başlıkları tanımlar (Örneğin: priority alanı yerine ekranda "Öncelik Seviyesi" yazar).


