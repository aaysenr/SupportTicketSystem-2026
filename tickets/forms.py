from django import forms # from django import forms: Django'nun form oluşturma, doğrulama ve widget yönetim modülünü içeri aktarır
from django.contrib.auth.models import User 
from .models import Ticket, TicketComment # Formun hangi veritabanı tablosunu temel alacağını belirtmek için Ticket ve TicketComment modelini içe aktarır.
from django.contrib.auth.forms import UserCreationForm 

class TicketForm(forms.ModelForm):  # Django'nun hazır ModelForm sınıfından türeyen bir form sınıfı tanımlar. Bu sayede Ticket modelindeki alanları otomatik olarak bir web formuna dönüştürür.
    """
    Ticket modeline dayalı form sınıfı.
    Kullanıcıdan alınacak alanları ve HTML stil (Bootstrap) giydirmelerini yönetir.
    """


    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Eğer kullanıcı yönetici değilse status ve assigned_to alanlarını kaldır
        if user and not user.is_staff:
            if 'status' in self.fields:
                del self.fields['status']
            if 'assigned_to' in self.fields:
                del self.fields['assigned_to']
        else:
            # Yöneticiler için 'assigned_to' liste seçeneklerinde sadece Yetkilileri (is_staff=True) göster
            if 'assigned_to' in self.fields:
                self.fields['assigned_to'].queryset = User.objects.filter(is_staff=True)
                self.fields['assigned_to'].empty_label = "Henüz Atanmadı (Atama Yap)"

 
   
    
    class Meta: # Django'ya bu formun hangi modeli kullanacağını ve hangi alanları göstereceğini bildirir
        model = Ticket # Formun Ticket veritabanı tablosundan türetileceğini belirtir.
        # Formda kullanıcının doldurmasını istediğimiz alanlar:
        fields = ['title', 'category', 'priority', 'status','assigned_to','description']

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
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'form-select'
            }), # EKLENDİ
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

        #status: Durum alanını bir açılır liste kutusu (<select>) olarak oluşturur ve Bootstrap'in form-select stilini uygular. Seçenekler models.py'daki STATUS_CHOICES listesinden otomatik doldurulur.




        
        labels = {
            'title': 'Talep Başlığı',
            'category': 'Kategori',
            'priority': 'Öncelik Seviyesi',
            'status': 'Talep Durumu',
            'assigned_to': 'Atanan Yönetici', # EKLENDİ
            'description': 'Detaylı Açıklama',
        }


        #labels: HTML etiketlerinin yanında belirecek olan metinleri (etiketleri) daha anlamlı ve kullanıcı dostu bir şekilde özelleştirmemizi sağlar. 
        #labels (Alan Etiketleri): Form alanlarının üzerinde kullanıcıya görünecek olan Türkçe başlıkları tanımlar (Örneğin: priority alanı yerine ekranda "Öncelik Seviyesi" yazar).



class CommentForm(forms.ModelForm): # Django'nun ModelForm sınıfından miras alarak TicketComment modeline bağlı bir form sınıfı oluşturur.
    """
    TicketComment modeline dayalı yorum ekleme formu.
    """


    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Eğer kullanıcı yönetici değilse "İç Not" onay kutusunu gizle
        if user and not user.is_staff:
            if 'is_internal' in self.fields:
                del self.fields['is_internal']


    class Meta:
        model = TicketComment # Formun bağlanacağı veritabanı tablosunu seçer.
        fields = ['content','is_internal'] # Formda gösterilecek alanlar.

        #model = TicketComment: Formun veritabanındaki TicketComment tablosuyla eşleşeceğini belirtir.

        #fields = ['content']: Formda yalnızca yorum içeriği alanının yer alacağını tanımlar. ticket, author ve created_at alanları hariç tutulur; bu bilgileri views.py içinde arka planda biz bağlayacağız.

        
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Yanıtınızı veya güncellemenizi buraya yazınız...'
            }),
            'is_internal': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        
        # widgets (Görsel Özelleştirme):

        # forms.Textarea: Yorum kutusunu çok satırlı metin alanı (<textarea>) olarak üretir.

        # 'class': 'form-control': Kutuyu Bootstrap form stiliyle tam genişlikli ve modern kenarlıklı hale getirir.

        # 'rows': 3: Kutunun dikey yüksekliğini 3 satır olarak sınırlar (detay sayfasını gereksiz şişirmez).

        # 'placeholder': Kullanıcı kutuya tıklamadan önce görünen gri rehber ipucu metnini tanımlar.





        labels = {
            'content': 'Yorum / Cevap Yazın',
            'is_internal': 'Bu bir gizli İç Nottur (Sadece Yöneticiler Görebilir)',
        }

        #labels: Kutunun hemen üstünde HTML <label> olarak görünecek başlığı Türkçeleştirir.


class UserRegisterForm(UserCreationForm):
    """
    Gelişmiş Kayıt Formu:
    - E-posta adresini zorunlu hale getirir.
    - Tüm form elemanlarına Bootstrap 'form-control' stilini giydirir.
    """
    email = forms.EmailField(
        required=True,
        label="E-posta Adresi",
        widget=forms.EmailInput(attrs={
            'placeholder': 'ornek@email.com'
        })
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tüm alanlara (Kullanıcı adı, e-posta, parola, parola tekrar) Bootstrap stili verelim
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
