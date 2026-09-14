from django import forms
from django.db.models import Count, Q
from django.contrib.auth.models import User
from .models import Ticket, TicketComment, TicketTag
from django.contrib.auth.forms import UserCreationForm 
from captcha.fields import CaptchaField 
import nh3
from .validators import validate_file_security

class TicketForm(forms.ModelForm):  # Django'nun hazır ModelForm sınıfından türeyen bir form sınıfı tanımlar. Bu sayede Ticket modelindeki alanları otomatik olarak bir web formuna dönüştürür.
    """
    Ticket modeline dayalı form sınıfı.
    Kullanıcıdan alınacak alanları ve HTML stil (Bootstrap) giydirmelerini yönetir.
    """

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Eğer kullanıcı personel değilse status alanını kaldır
        if user and not user.is_staff:
            if 'status' in self.fields:
                del self.fields['status']

        # Yöneticilere atama yapma yetkisi SADECE Süper Yöneticilere açıktır
        profile = getattr(user, 'profile', None) if user else None
        is_superadmin = user and (user.is_superuser or (profile and profile.role == 'superadmin'))

        if not is_superadmin:
            if 'assigned_to' in self.fields:
                del self.fields['assigned_to']
        else:
            if 'assigned_to' in self.fields:
                self.fields['assigned_to'].queryset = User.objects.filter(is_staff=True)
                self.fields['assigned_to'].empty_label = "Henüz Atanmadı (Atama Yap)"

        if 'tags' in self.fields:
            # En çok kullanılan ilk 10 etiketi listele
            top_tag_ids = list(TicketTag.objects.annotate(usage=Count('tickets')).order_by('-usage', 'name')[:10].values_list('id', flat=True))
            if self.instance and self.instance.pk:
                existing_ids = list(self.instance.tags.values_list('id', flat=True))
                combined_ids = list(dict.fromkeys(top_tag_ids + existing_ids))
                self.fields['tags'].queryset = TicketTag.objects.filter(id__in=combined_ids)
            else:
                self.fields['tags'].queryset = TicketTag.objects.filter(id__in=top_tag_ids)

            self.fields['tags'].widget = forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
            self.fields['tags'].widget.choices = self.fields['tags'].choices
            self.fields['tags'].required = False
            self.fields['tags'].label = "Etiketler"

    def clean_tags(self):
        tags = self.cleaned_data.get('tags')
        if tags and len(tags) > 5:
            raise forms.ValidationError("En fazla 5 etiket seçebilirsiniz.")
        return tags

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            validate_file_security(attachment)
        return attachment

    def clean_description(self):
        description = self.cleaned_data.get('description', '')
        if description:
            # Quill editöründen gelen HTML içeriğini zararlı XSS kodlarından arındır
            description = nh3.clean(
                description,
                tags={'p', 'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                      'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'br', 'span', 'a'},
                attributes={
                    'a': {'href', 'title', 'target'},
                    '*': {'class'}
                }
            )
        return description

    class Meta:
        model = Ticket
        fields = ['title', 'category', 'priority', 'status', 'assigned_to', 'tags', 'is_public', 'description', 'attachment']

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
            }), 
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Yaşadığınız sorunu detaylıca açıklayınız...'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.png,.jpg,.jpeg,.pdf,.zip,.log',
                'placeholder': 'Bir dosya veya görsel seçin...'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input ms-0'
            }),
            'tags': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-check-input'
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
            'assigned_to': 'Atanan Yönetici',
            'description': 'Detaylı Açıklama',
            'attachment': 'Ek Dosya / Görsel (PNG, JPG, PDF, LOG)',
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


    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            validate_file_security(attachment)
        return attachment

    def clean_content(self):
        content = self.cleaned_data.get('content', '')
        if content:
            content = nh3.clean(
                content,
                tags={'p', 'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                      'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'br', 'span', 'a'},
                attributes={
                    'a': {'href', 'title', 'target'},
                    '*': {'class'}
                }
            )
        return content

    class Meta:
        model = TicketComment # Formun bağlanacağı veritabanı tablosunu seçer.
        fields = ['content','is_internal','attachment'] # Formda gösterilecek alanlar.

        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Yanıtınızı veya güncellemenizi buraya yazınız...'
            }),
            'is_internal': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.png,.jpg,.jpeg,.pdf,.zip,.log',
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
            'attachment': 'Ek Dosya / Görsel',
        }


class CommentEditForm(forms.ModelForm):
    """
    Var olan bir yorumu güvenli şekilde düzenlemek için model formu.
    """
    class Meta:
        model = TicketComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Yorumunuzu güncelleyiniz...'
            })
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '')
        if content:
            content = nh3.clean(
                content,
                tags={'p', 'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                      'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'br', 'span', 'a'},
                attributes={
                    'a': {'href', 'title', 'target'},
                    '*': {'class'}
                }
            ).strip()
        if not content:
            raise forms.ValidationError("Yorum metni boş bırakılamaz.")
        return content


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

    captcha = CaptchaField(label="Güvenlik Kodu")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'email']


    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            return email

        if User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError("Bu e-posta adresi zaten başka bir hesap tarafından kullanılıyor.")

        inactive_user = User.objects.filter(email__iexact=email, is_active=False).first()
        if inactive_user:
            self.inactive_user = inactive_user
            return email

        return email
        

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tüm alanlara (Kullanıcı adı, e-posta, parola, parola tekrar) Bootstrap stili verelim
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'



class UserProfileForm(forms.ModelForm):
    """
    Kullanıcı profil bilgilerini (ad, soyad, kullanıcı adı, e-posta ve avatar) güncelleme formu.
    Güvenlik için mevcut şifre onayı gerektirir.
    """
    first_name = forms.CharField(max_length=150, required=False, label="Ad")
    last_name = forms.CharField(max_length=150, required=False, label="Soyad")
    email = forms.EmailField(required=True, label="E-posta Adresi")
    avatar = forms.ImageField(
        required=False,
        label="Profil Fotoğrafı (Opsiyonel)",
        validators=[validate_file_security],
        widget=forms.FileInput(attrs={'accept': 'image/*'})
    )
    
    # Güvenlik için eklendi:
    current_password = forms.CharField(
        label="Mevcut Şifreniz (Onay İçin)",
        widget=forms.PasswordInput(attrs={'placeholder': 'Değişiklikleri onaylamak için mevcut şifrenizi girin'}),
        required=True
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Görünümden gelen aktif kullanıcı nesnesi
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Bu e-posta adresi başka bir kullanıcı tarafından kullanılıyor.")
        return email

    # Şifre Doğrulama Kontrolü:
    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if self.user and not self.user.check_password(current_password):
            raise forms.ValidationError("Profil bilgilerinizi güncellemek için mevcut şifrenizi doğru girmelisiniz.")
        return current_password

    def save(self, commit=True):
        user = super().save(commit=commit)
        if 'avatar' in self.cleaned_data:
            avatar = self.cleaned_data.get('avatar')
            if avatar:
                from .models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=user)
                if profile.avatar and profile.avatar.name and profile.avatar != avatar:
                    profile.avatar.delete(save=False)
                profile.avatar = avatar
                profile.save()
        return user


from django.contrib.auth.forms import PasswordResetForm

class CustomPasswordResetForm(PasswordResetForm):
    """
    Şifre sıfırlama formu:
    Hem e-posta gönderir hem de test/geliştirme ortamında şifre sıfırlama bağlantısını
    konsola (terminale) net bir kutu şeklinde yazdırır.
    """
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        super().send_mail(subject_template_name, email_template_name,
                          context, from_email, to_email, html_email_template_name)
        
        import logging
        from django.conf import settings
        logger = logging.getLogger(__name__)

        reset_url = f"{context.get('protocol')}://{context.get('domain')}/reset/{context.get('uid')}/{context.get('token')}/"
        user_obj = context.get('user')
        username = getattr(user_obj, 'username', 'Kullanıcı')
        logger.info("[ŞİFRE SIFIRLAMA] E-posta gönderildi: Alıcı=%s, Kullanıcı=%s", to_email, username)

        if getattr(settings, 'DEBUG', False):
            print("\n" + "=" * 65)
            print(" [TEST / GELİŞTİRME] ŞİFRE SIFIRLAMA E-POSTASI GÖNDERİLDİ")
            print("=" * 65)
            print(f" Alıcı E-Posta : {to_email}")
            print(f" Kullanıcı     : {username}")
            print(f" Sıfırlama URL : {reset_url}")
            print("=" * 65 + "\n")


