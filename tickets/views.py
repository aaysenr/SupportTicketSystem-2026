from django.shortcuts import render, get_object_or_404, redirect
from .models import Ticket
from .forms import TicketForm,CommentForm, UserRegisterForm # CommentForm sınıfını detay görünümünde kullanabilmek için içeri aktarır.
from django.contrib.auth.models import User
from django.db.models import Q  # Karmaşık arama sorguları (OR işlemleri) için Q nesnesini içeri aktarıyoruz
#Q Nesnesi: Normalde Django ORM'de .filter(title=..., description=...) yazıldığında araya AND (VE) koyar. SQL'deki OR (VEYA) mantığını kurabilmek için Q nesnesini içeri aktarırız.
from django.core.mail import send_mail
from .models import EmailVerification
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash 
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm #
from .forms import TicketForm, CommentForm, UserRegisterForm, UserProfileForm 
from .models import Ticket, TicketComment, Category, EmailVerification, TicketActivityLog
from .models import Ticket, TicketComment, Category, EmailVerification, TicketActivityLog, Notification


# render: Django'nun HTML şablonlarını (template) verilerle birleştirip kullanıcıya sunmasını sağlayan pratik bir yardımcı fonksiyondur.
# from .models import Ticket: Bulunduğumuz uygulama klasöründeki (.) models.py dosyasından veritabanı tablomuzu temsil eden Ticket modelini projeye dahil eder.
#get_object_or_404: Veritabanından nesne çekerken hata yönetimini (Exception Handling) otomatik yapan kısayoldur.

# redirect: Kullanıcıyı bir işlem bittikten sonra başka bir URL'e yönlendiren fonksiyondur. Sayfanın yenilenmesiyle formun mükerrer (çift) gönderilmesini engeller.

# from .forms import TicketForm: TicketForm sınıfını kullanabilmek için içeri alır.

# from django.contrib.auth.models import User: Oturum açmamış test durumlarında kullanıcı atayabilmek için Django'nun kullanıcı modelini içeri aktarır.


# Oturum Yönetimi ve Güvenlik İçin Gerekli İçe Aktarmalar
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages

"""
login, logout, authenticate:

authenticate: Kullanıcı adı ve şifrenin veritabanındaki hash'lenmiş şifreyle eşleşip eşleşmediğini kontrol eder.

login: Başarılı giriş sonrası kullanıcının tarayıcısına güvenli bir session (oturum) çerezi bırakır.

logout: Kullanıcının aktif oturum çerezini siler ve oturumu kapatır.

UserCreationForm, AuthenticationForm: Django'nun şifre kurallarını (en az 8 karakter, karmaşıklık vb.) ve güvenlik kontrollerini otomatik yapan hazır form sınıflarıdır.

@login_required: Bir görünümün (View) başına konulduğunda, oturum açmamış kullanıcıların o sayfayı açmasını engelleyen bekçidir (decorator).

messages: İşlem tamamlandığında (Örn: "Hesap oluşturuldu", "Yorum eklendi") ekrana bir kerelik Bootstrap alert kutusu basmamızı sağlayan mesaj çerçevesidir.
"""

import json
from django.db.models import Count
from django.utils import timezone
from .models import Category

@login_required
def admin_dashboard_view(request):
    """
    Yöneticiler için İstatistik ve Analiz Dashboard'u.
    """
    # Güvenlik Kontrolü: Yalnızca yöneticiler girebilir!
    if not request.user.is_staff:
        messages.error(request, "Bu sayfayı görüntüleme yetkiniz yok!")
        return redirect('ticket_list')

    # 1. Temel Metrikler
    total_tickets = Ticket.objects.count()
    open_tickets = Ticket.objects.filter(status='open').count()
    in_progress_tickets = Ticket.objects.filter(status='in_progress').count()
    resolved_tickets = Ticket.objects.filter(status='resolved').count()
    urgent_tickets = Ticket.objects.filter(priority='urgent').count()

    # 2. Bu Ay Açılan ve Bu Ay Çözülen Talepler
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    resolved_this_month = Ticket.objects.filter(status='resolved', updated_at__gte=first_day_of_month).count()
    created_this_month = Ticket.objects.filter(created_at__gte=first_day_of_month).count()

    # 3. Kategori Dağılımı Verileri (Chart.js İçin)
    categories = Category.objects.annotate(ticket_count=Count('tickets'))
    category_labels = [cat.name for cat in categories]
    category_counts = [cat.ticket_count for cat in categories]

    # 4. Öncelik Dağılımı Verileri
    priority_data = {
        'Düşük': Ticket.objects.filter(priority='low').count(),
        'Orta': Ticket.objects.filter(priority='medium').count(),
        'Yüksek': Ticket.objects.filter(priority='high').count(),
        'Acil': Ticket.objects.filter(priority='urgent').count(),
    }

    context = {
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'urgent_tickets': urgent_tickets,
        'resolved_this_month': resolved_this_month,
        'created_this_month': created_this_month,
        
        # Chart.js'in JSON formatında okuyabilmesi için:
        'category_labels_json': json.dumps(category_labels),
        'category_counts_json': json.dumps(category_counts),
        'priority_labels_json': json.dumps(list(priority_data.keys())),
        'priority_counts_json': json.dumps(list(priority_data.values())),
    }

    return render(request, 'tickets/dashboard.html', context)



def verify_email(request):
    user_id = request.session.get('unverified_user_id')
    if not user_id:
        return redirect('register')
    
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        entered_code = request.POST.get('code', '').strip()
        try:
            verification = user.email_verification
            if verification.code == entered_code and verification.is_valid():
                # Kod doğru ve süresi geçerli!
                user.is_active = True
                user.save()
                
                # Oturumu temizle ve otomatik giriş yaptır
                del request.session['unverified_user_id']
                login(request, user)
                messages.success(request, f"Tebrikler {user.username}! E-postanız başarıyla doğrulandı ve hesabınız aktifleştirildi.")
                return redirect('ticket_list')
            else:
                messages.error(request, "Girdiğiniz doğrulama kodu hatalı veya süresi dolmuş!")
        except EmailVerification.DoesNotExist:
            messages.error(request, "Doğrulama bilgisi bulunamadı.")

    return render(request, 'tickets/verify_email.html', {'user': user})



# --- 1. KULLANICI OTURUM GÖRÜNÜMLERİ (AUTH VIEWS) ---

def register_user(request):
    """
    Yeni kullanıcı kayıt görünümü.
    Eğer kullanıcı zaten giriş yapmışsa direkt liste sayfasına yönlendirir.
    """
    if request.user.is_authenticated:
        return redirect('ticket_list')
    
    #if request.user.is_authenticated: Zaten giriş yapmış olan bir kullanıcının tekrar kayıt sayfasına girmesini engeller ve ana listeye yönlendirir.


    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        # Kullanıcının girdiği kullanıcı adı ve şifre ikilisini doğrular.
        if form.is_valid():

            # 1. Kullanıcıyı henüz pasif (is_active=False) olarak kaydediyoruz
            user = form.save(commit=False)
            user.is_active = False
            user.save()

             # 2. Onay kodu oluşturuyoruz
            verification, created = EmailVerification.objects.get_or_create(user=user)
            verification.generate_code()

             # 3. E-posta gönderiyoruz
            send_mail(
                subject="E-Posta Dogrulama Kodu",
                message=f"Merhaba {user.username},\n\nDestek Sistemine kayit isleminizi tamamlamak için dogrulama kodunuz: {verification.code}\n\nBu kod 10 dakika süreyle gecerlidir.",
                from_email=None,
                recipient_list=[user.email],
            )
            # 4. Kullanıcı ID'sini oturuma kaydedip doğrulama sayfasına yönlendiriyoruz
            request.session['unverified_user_id'] = user.id
            messages.info(request, "Lütfen e-posta adresinize gönderilen 6 haneli doğrulama kodunu girin.")
            return redirect('verify_email')
        else:
            messages.error(request, "Lütfen formdaki hataları düzeltin.")
        #else: Eğer form geçerli değilse (Hata varsa)...
    
    else:
        form = UserRegisterForm()
    #else: Eğer POST isteği yoksa (Sayfa ilk açılıyorsa)...
    context = {'form': form} #form: HTML şablonunda kullanmak üzere form nesnesini bir sözlüğe ekler.
    return render(request, 'tickets/register.html', context) 



def login_user(request):
    """
    Kullanıcı giriş görünümü.
    """
    if request.user.is_authenticated:
        return redirect('ticket_list')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username') #cleaned_data: Formdan gelen verileri temizleyip sözlük formatında döndüren yapıdır.
            password = form.cleaned_data.get('password') #password: Şifreyi güvenli bir şekilde alır.
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Tekrar hoş geldiniz, {username}!")
                return redirect('ticket_list')
            else:
                messages.error(request, "Kullanıcı adı veya parola hatalı.")
        else:
            messages.error(request, "Geçersiz giriş bilgileri.")
    else:
        form = AuthenticationForm()
    context = {'form': form}
    return render(request, 'tickets/login.html', context)


    #AuthenticationForm(request, data=request.POST): Giriş verilerini alan formdur.

    #authenticate(...): Veritabanında bu kullanıcı adı ve parola doğru mu diye sorgular. Doğruysa User nesnesi döner, yanlışsa None döner.

    #login(request, user): Oturumu başlatır.





def logout_user(request):
    """
    Kullanıcı oturum kapatma görünümü.
    """
    logout(request)
    messages.info(request, "Oturumunuz başarıyla kapatıldı.")
    return redirect('login')

#logout(request): Oturumu sıfırlar.

#redirect('login'): Çıkış yapan kullanıcıyı tekrar giriş yapabileceği login sayfasına postalar.








"""
@login_required Yapısı Nasıl Çalışır?
Anonim bir ziyaretçi /ticket/new/ veya /ticket/1/ sayfasına girmeye çalışırsa
Django isteği keser ve kullanıcıyı otomatik olarak /accounts/login/?next=/ticket/new/ adresine yönlendirir. 
Giriş yapmadan içerik gösterilmez.





Artık @login_required sayesinde fonksiyon çalıştığı anda kullanıcının oturum açtığı kesinleştiği için:
geçici else dalları (ticket.created_by = User.objects.first() # <-- GEÇİCİ KOD)
tamamen kaldırıldı ve doğrudan request.user atandı.
"""















# --- 2. DESTEK TALEBİ GÖRÜNÜMLERİ (KORUMALI) ---

@login_required
def ticket_list(request):

    # Django'da bir sayfa istendiğinde çalışacak fonksiyon tanımlanır.

    # request: Tarayıcıdan gelen HTTP isteğine dair tüm bilgileri (kullanıcı oturumu, ip adresi, form verileri vb.) taşıyan zorunlu parametredir.
     
    """
    Talepleri listeleyen görünüm.
    - Yöneticiler (is_staff) TÜM talepleri görür.
    - Normal kullanıcılar SADECE kendi açtıkları talepleri görür.
    """

    # 1. Kullanıcının rolüne göre temel talep kümesini belirliyoruz (Performans için select_related eklendi)
    if request.user.is_staff:
         base_tickets = Ticket.objects.all().select_related('created_by', 'category', 'assigned_to')
    else:
        base_tickets = Ticket.objects.filter(created_by=request.user).select_related('created_by', 'category', 'assigned_to')


    # base_tickets (Temel Veri Havuzu): Filtreleme yapılmadan önceki ham yetki havuzudur. 
    # İstatistikler bu temel küme üzerinden hesaplanır; böylece kullanıcı arama kutusuna bir kelime yazıp tabloyu daraltsa bile üstteki toplam sayaçlar doğru genel toplamı göstermeye devam eder.

    #request.user.is_staff: Kullanıcının yönetici / teknik destek ekibinde olup olmadığını kontrol eder.

    #filter(created_by=request.user): Standart kullanıcıya ait olmayan talepleri daha SQL seviyesinde ayıklar (WHERE created_by_id = ?). 
    # Arama ve filtreler de sadece bu daraltılmış liste üzerinde çalışır.
    
    # 2. İstatistik Sayaçları (Django ORM .count() Metodu)
    total_count = base_tickets.count()
    open_count = base_tickets.filter(status='open').count()
    in_progress_count = base_tickets.filter(status='in_progress').count()
    resolved_count = base_tickets.filter(status='resolved').count()
    urgent_count = base_tickets.filter(priority='urgent').count()
    

    #total_count = base_tickets.count(): Kullanıcının yetkisi dahilindeki toplam talep adedi.

    #.filter(status='open').count(): Sadece durumu open (Açık) olanları sayar.

    #.filter(status='in_progress').count(): Sadece durumu in_progress (Devam Ediyor) olanları sayar.

    #.filter(status='resolved').count(): Sadece durumu resolved (Çözüldü) olanları sayar.

    #.filter(priority='urgent').count(): Kritik ve anında müdahale gerektiren urgent (Acil) öncelikli talepleri sayar.
    


    # 3. URL Arama ve Filtreleme İşlemleri
    tickets = base_tickets
    #Bağımsız Filtreleme: Arama ve dropdown filtreleri tickets değişkeni üzerinden yürütülür, base_tickets sayaçları etkilenmez.
    
    # URL'den gelen GET parametrelerini yakalıyoruz (Örn: /?q=yazici&status=open&priority=urgent)
    search_query = request.GET.get('q', '')
    selected_status = request.GET.get('status', '')
    selected_priority = request.GET.get('priority', '')


    #request.GET.get('anahtar', ''): Tarayıcı adres çubuğundaki parametreleri okur (Örn: /?q=yazici&status=open).
    #Eğer parametre URL'de yoksa varsayılan olarak boş metin ('') döner, hata fırlatmaz.


    # Kelime Arama Filtresi (Başlıkta VEYA Açıklamada arar - icontains: büyük/küçük harf duyarsız arama)
    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    #Q(title__icontains=search_query) | Q(description__icontains=search_query): Django ORM'e "ya başlıkta (title) aradığımız kelimeyi içeriyorsa VEYA açıklama (description) kısmında içeriyorsa getir" deriz.
    #icontains:insensitive contain (küçük/büyük harf duyarsız içerir). SQL'deki ILIKE operatörünün Django karşılığıdır. Yani 'Yazıcı' ve 'yazıcı' aramalarını aynı sonucu verir.
    # | : Python'daki VEYA operatörüdür. Django ORM, Q nesneleri ile kullanıldığında bunu SQL'deki OR operatörüne çevirir.
    # tickets.filter(...): Mevcut ticket listesini (ki başlangıçta tüm liste idi) bu yeni kritere göre daraltır/filtrelersin.

    # | Operatörü: Q(...) | Q(...) ifadesi SQL'deki OR bağlacıdır.
    # __icontains: "Case-insensitive contains" anlamına gelir. Metnin büyük/küçük harf duyarsız olarak aranan kelimeyi içerip içermediğini denetler.
    # Oluşan SQL: WHERE (title LIKE '%yazici%' OR description LIKE '%yazici%')



    # Durum Filtresi
    if selected_status:
        tickets = tickets.filter(status=selected_status)
    
    # selected_status: Eğer kullanıcı dropdown menülerden bir durum veya öncelik seçtiyse sorguya AND status = 'open' şeklinde ek filtre ekler.
    # tickets.filter(status=selected_status): Mevcut ticket listesini, sadece durumu seçilen durumla eşleşen kayıtlar kalacak şekilde günceller.
    # Eğer durum seçilmemişse bu satır atlanır ve filtreleme yapılmaz.
    #Örn: status=open ise -> WHERE status='open' sorgusu eklenir.


    # Öncelik Filtresi
    if selected_priority:
        tickets = tickets.filter(priority=selected_priority)

    # selected_priority: Eğer kullanıcı dropdown menülerden bir durum veya öncelik seçtiyse sorguya AND status = 'open' şeklinde ek filtre ekler.
    # tickets.filter(priority=selected_priority): Mevcut ticket listesini, sadece önceliği seçilen öncelikle eşleşen kayıtlar kalacak şekilde günceller.
    # Eğer öncelik seçilmemişse bu satır atlanır ve filtreleme yapılmaz.
    # Örn: priority=urgent ise -> WHERE priority='urgent' sorgusu eklenir.
    
    
    
    
    # 4. Şablona hem talepleri hem de istatistik sayılarını gönderiyoruz
    # HTML şablonuna hem filtrelenmiş verileri hem de seçili filtre durumlarını gönderiyoruz
    
    # HTML şablonuna göndereceğimiz verileri bir dictionary (sözlük) haline getiriyoruz
    context = {
        'tickets': tickets,
        'search_query': search_query,
        'selected_status': selected_status,
        'selected_priority': selected_priority,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,

        # İstatistik Değişkenleri
        #Hesaplanan 5 ayrı sayaç context sözlüğüne eklenerek HTML şablonuna gönderilir.
        'total_count': total_count,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'urgent_count': urgent_count,

    }
    # Veritabanından çekilen veriyi HTML şablonuna aktarabilmek için bir Python dictionary (sözlük) yapısı oluşturulur.
    # Sözlükteki 'tickets' anahtarı, HTML tarafında bu verilere erişmek için kullanacağımız değişken adı olacaktır.

    """
    Formu Hatırlama: search_query, selected_status ve selected_priority şablona geri gönderilir; 
    böylece filtreleme yapıldıktan sonra kullanıcının yazdığı arama metni ve seçtiği dropdown kutusu seçili kalır.
    STATUS_CHOICES & PRIORITY_CHOICES: Modelde tanımladığımız durum ve öncelik listelerini HTML tarafında <select> seçenekleri olarak döngüye sokmak için göndeririz.
    """



    # Şablonu ve veriyi birleştirip kullanıcıya HTML yanıtı dönüyoruz
    return render(request, 'tickets/ticket_list.html', context)

    #render fonksiyonu 3 temel bileşeni bir araya getirir:
    #request: Kullanıcı isteği.
    #tickets/ticket_list.html: Verilerin basılacağı HTML şablonunun yolu.
    #context: Şablona gönderilecek veri paketi.
    #Bu işlem sonucunda Django dinamik olarak HTML içeriğini üretir ve tarayıcıya yanıt olarak gönderir.
    #Çalışma Mantığı Özeti:
    #Tarayıcı İsteği ➔ ticket_list (View) ➔ Ticket.objects.all() (Veritabanı) ➔ context (Veri Paketleme) ➔ ticket_list.html (Render) ➔ Kullanıcıya Gösterim



@login_required
def ticket_detail(request, pk):

    """
    Tek bir destek talebinin detayını ve yorumlarını gösteren görünüm (View)
    """

    #def ticket_detail(...): Detay sayfamızın iş mantığını yürüten View fonksiyonudur.

    #request: Tarayıcıdan gelen HTTP isteğini (giriş yapan kullanıcı bilgisi, oturum vb.) taşır.

    #pk (Primary Key): URL'den gelen dinamik ID numarasıdır (Örneğin kullanıcı /ticket/5/ adresine girerse pk = 5 olur).
    
    
   
    # 1. get_object_or_404: Veritabanında belirtilen pk (primary key / id) değerine sahip Ticket'ı arar.
    # Bulursa 'ticket' değişkenine atar, bulamazsa kullanıcıya 404 hatası döner.
    # 1. get_object_or_404: İlişkili verileri tek sorguda çek
    ticket = get_object_or_404(Ticket.objects.select_related('created_by', 'category', 'assigned_to'), pk=pk)

    """
    Ticket: Arama yapılacak model/tablo.

    pk=pk: Veritabanındaki id sütunu, fonksiyona gelen pk değerine eşit olan satırı bulur.

    Çalışma Mantığı:

    Normalde Ticket.objects.get(pk=pk) yazsaydık ve o ID'de bir talep olmasaydı sistem DoesNotExist hatası vererek 500 Server Error ile çökerdi.

    get_object_or_404 ise arka planda otomatik bir try-except bloğu çalıştırarak kayıt yoksa kullanıcıya standart bir 404 Sayfa Bulunamadı ekranı döner.
    
    """

    
    # Güvenlik & Gizlilik Kontrolü: Talebi oluşturan kişi veya yönetici değilse engelle
    if not request.user.is_staff and ticket.created_by != request.user:
        messages.error(request, "Bu destek talebini görüntüleme yetkiniz yok!")
        return redirect('ticket_list')

        #IDOR Güvenlik Duvarı: Kullanıcı ne yöneticiyse ne de o talebin bizzat sahibiyse, işlem hemen kesilir; 
        #kırmızı bir hata mesajıyla ana sayfaya postalanır.



    # Sistem log metinlerini yorumlar akışından süzüp sadece gerçek kullanıcı yorumlarını çekiyoruz
    comments = ticket.comments.exclude(content__startswith='Güncelleme yapıldı').exclude(content__startswith='⚙️ Güncelleme yapıldı').exclude(content='Talep detayları güncellendi.')

    if not request.user.is_staff:
       comments = comments.filter(is_internal=False)

    comments = comments.select_related('author')

  

    """
    Ters İlişki (Reverse Relation): models.py dosyasında TicketComment modelini yazarken ticket = ForeignKey(Ticket, related_name='comments') tanımlaması yapmıştık.

    Bu sayede ne Yapar? 
    
    Django ORM arka planda SELECT * FROM tickets_ticketcomment WHERE ticket_id = 3 ORDER BY created_at ASC sorgusunu çalıştırır 
    ve doğrudan bu talebe yazılmış yorumları kronolojik listeler.
    """
    
    
    if request.method == 'POST':
        # Yorum gönderme butonu tıklandıysa (POST isteği)
        comment_form = CommentForm(request.POST, request.FILES, user=request.user)
        # request.FILES: Kullanıcının form üzerinden yüklediği dosya verilerini tutan sözlüktür.
        # request.POST: Kullanıcının form üzerinden gönderdiği metin verilerini (başlık, açıklama, kategori vb.) tutar.
        # user=request.user: Formun içine, şu an giriş yapmış olan kullanıcının bilgilerini "yazar" olarak kaydeder.    

        if comment_form.is_valid():

            #if request.method == 'POST': Kullanıcı detay sayfasındaki "Yorum Yap / Gönder" butonuna bastığında çalışır.

            #CommentForm(request.POST): Kullanıcının form kutusuna yazdığı metni forma doldurur.

            #comment_form.is_valid(): Yorum alanının boş bırakılıp bırakılmadığını veya kural ihlali olup olmadığını denetler.






            # Yorum nesnesini oluştur ama veritabanına henüz yazma (ticket ve author bilgisi eksik!)
            comment = comment_form.save(commit=False)
            
            # Yorumun yazıldığı talebi (ticket) ilişkilendir
            comment.ticket = ticket


            #commit=False: Yorum nesnesini bellekte oluşturur ama henüz SQL INSERT yapmaz.

            #comment.ticket = ticket (Kritik Adım): TicketComment modeli hangi talebe yorum yapıldığını bilmek zorundadır (ForeignKey). 
            #Kullanıcıya formda talep seçtirmedik; URL'den çektiğimiz mevcut ticket nesnesini yoruma burada arka planda bağlıyoruz.
            


            # Giriş yapmış olan oturum sahibini doğrudan yazar olarak atıyoruz
            comment.author = request.user
            comment.save()


            
            # CANLI BİLDİRİM: Yorumu yazan kişi talep sahibi değilse bildirim oluştur
            if comment.author != ticket.created_by:
                Notification.objects.create(
                    recipient=ticket.created_by,
                    actor=comment.author,
                    ticket=ticket,
                    message=f"#{ticket.ticket_number} talebinize {comment.author.username} tarafından yanıt eklendi."
                )
            # E-POSTA BİLDİRİMİ
            if comment.author != ticket.created_by and ticket.created_by.email:
                send_notification_email(
                    subject=f"[Destek Talebi] #{ticket.ticket_number} Talebinize Yeni Yanıt Geldi",
                    message=f"Merhaba {ticket.created_by.username},\n\n#{ticket.ticket_number} numaralı '{ticket.title}' başlıklı destek talebinize {comment.author.username} tarafından yeni bir yanıt eklendi:\n\n\"{comment.content}\"\n\nTalebi ve detayları görüntülemek için sisteme giriş yapabilirsiniz.\n\nİyi çalışmalar dileriz.",
                    recipient_list=[ticket.created_by.email]
                )

            messages.success(request, "Yorumunuz başarıyla eklendi.")


            #comment.author: Yorumu yazan kişiyi (author) oturum açmış kullanıcı olarak atar.

            #comment.save(): Talebi, yazarı ve içeriği artık eksiksiz olan yorumu veritabanına fiziksel olarak kaydeder.


            #return redirect('ticket_detail', pk=ticket.pk): İşlem başarılı olduğu için tarayıcıyı 
            #tam olarak aynı sayfanın (talebin detay sayfası) yenilenmiş haline yönlendirir. 
            #Böylece kullanıcı, sayfayı manuel yenilemeden yeni yorumunu hemen listede görür.

            # Sayfayı yenileyerek yorumun anında görünmesini sağla
            return redirect('ticket_detail', pk=ticket.pk)

            #Sayfayı Yeniden Yükleme (PRG Prensibi): Kayıt bitince sayfayı temiz bir GET isteğiyle yeniden açar. 
            #Böylece yeni yazılan yorum anında sayfada belirir ve kullanıcı sayfayı yenilediğinde (F5) aynı yorum mükerrer eklenmez.



    else:
        # Sayfa ilk kez açıldıysa (GET isteği) boş yorum formu üret
        comment_form = CommentForm(user=request.user)



        #Sayfaya ilk kez girildiğinde (GET), 
        #kullanıcıya sunulmak üzere boş bir CommentForm() üretilir 
        #ve context paketine eklenerek HTML şablonuna gönderilir.




    
    
    # 3. HTML şablonuna gönderilecek veri paketini hazırlınır
    context = {
        'ticket': ticket,
        'comments': comments,
        'comment_form': comment_form,
        'activity_logs': ticket.activity_logs.all(),
    }

    """
    Context Sözlüğü (Veri Paketi): Python tarafında hazırladığımız verileri HTML şablonuna taşımak için hazırlanan çantadır.

    'ticket': Tek bir talebin tüm özelliklerini (title, description, status vb.) tutar.

    'comments': O talebe ait yorum listesini tutar.

    """


    # 4. Şablonu render edip kullanıcıya sunuyoruz
    return render(request, 'tickets/ticket_detail.html', context)

    """
    render(...): tickets/ticket_detail.html dosyasını açar, 
    içindeki {{ ticket.title }} ve {% for comment in comments %} gibi
    dinamik alanları gerçek verilerle doldurur 
    ve tarayıcıya saf bir HTML sayfası olarak döndürür.
    """

@login_required
def ticket_create(request): 
    """
    Yeni destek talebi oluşturma görünümü (View).
    GET isteği geldiğinde boş form gösterir.
    POST isteği geldiğinde formu doğrular ve kaydeder.
    """

    # Bir web formunda iki aşama vardır: 
    # Formu ekranda görmek (GET) ve doldurup sunucuya göndermek (POST). 
    # Kod bu ayrımı if request.method == 'POST' kontrolüyle yönetir.

    if request.method == 'POST':
        #Kullanıcı formu doldurup Gönder butonuna bastıysa (POST isteği)
        # Kullanıcı formu ilk kez açtığında içi boş, temiz bir form nesnesi üretir ve ticket_form.html şablonuna gönderir.
        form = TicketForm(request.POST, request.FILES, user=request.user)
        # request.FILES: Kullanıcının form üzerinden yüklediği dosya verilerini tutan sözlüktür.
        # request.POST: Kullanıcının form üzerinden gönderdiği metin verilerini (başlık, açıklama, kategori vb.) tutar.
        # user=request.user: Formun içine, şu an giriş yapmış olan kullanıcının bilgilerini "yazar" olarak kaydeder.
        # Bir form HTML sayfasıdır. Kullanıcı bu formu doldurup "Gönder" (Submit) butonuna tıkladığında, tarayıcı sayfanın URL'ine bir POST isteği gönderir.
        # Kullanıcının girdiği verileri (request.POST) alıp forma yükler.

        if form.is_valid():
            # Form kurallara uygunsa (boş bırakılan zorunlu alan yoksa vb.)
            # Girilen verilerin kurallara (zorunlu alanlar, maksimum karakter sınırları vb.) uygunluğunu doğrular. 
            # Geçersizse hatalarla birlikte formu ekrana geri basar.


            """
            models.py dosyasında Ticket modelinin created_by alanını zorunlu (NOT NULL) tanımladık. 
            Ancak TicketForm içinde bu alanı güvenlik nedeniyle kullanıcıya göstermedik (fields listesine eklemedik).
            """

            # commit=False: Nesneyi oluştur ama henüz veritabanına kaydetme (Çünkü created_by alanı henüz eksik!)
            ticket = form.save(commit=False)
            # ticket = form.save(commit=False): Formdaki verilerden bir Ticket nesnesi üretir ama henüz veritabanına kaydetmez, bellekte bekletir.
            


            # Talebi oluşturan kişi oturum açmış olan kullanıcıdır
            ticket.created_by = request.user

            # ticket.created_by = request.user: Eksik kalan "oluşturan kullanıcı" bilgisini arkadan sisteme giriş yapmış olan kullanıcı olarak atar.
            
            # Şimdi veritabanına tam kaydı gerçekleştirebiliriz
            ticket.save()
            #ticket.save(): Nesne artık eksiksiz olduğu için veritabanına nihai kaydı (INSERT INTO) gerçekleştirir.
            
            TicketActivityLog.objects.create(
               ticket=ticket,
               actor=request.user,
               action="Destek talebi oluşturuldu."
            )



        # E-POSTA BİLDİRİMİ: Kullanıcıya Teyit Maili Gönder
        if ticket.created_by.email:
            send_notification_email(
                subject=f"[Destek Talebi] #{ticket.ticket_number} Talebiniz Başarıyla Alındı",
                message=f"Merhaba {ticket.created_by.username},\n\n#{ticket.ticket_number} numaralı '{ticket.title}' başlıklı destek talebiniz sisteme kaydolmuştur.\n\nDestek ekibimiz en kısa sürede talebinizi inceleyip yanıtlayacaktır.\n\nİyi günler dileriz.",
                recipient_list=[ticket.created_by.email]
            )

            messages.success(request, "Destek talebiniz başarıyla oluşturuldu.") 


            # İşlem bitince oluşturulan talebin detay sayfasına yönlendir
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        # Sayfaya ilk kez girildiyse (GET isteği) boş form üret
        form = TicketForm(user=request.user)
        # form = TicketForm(): Tarayıcıdan henüz POST isteği gelmediği için (sayfa ilk açılış anı), içi boş temiz bir TicketForm nesnesi oluşturulur.

    context = {
        'form': form
    }
    # context = {'form': form}: İçinde doldurulacak boş form nesnesini barındıran paketi HTML şablonuna gönderir.

    return render(request, 'tickets/ticket_form.html', context)

    # Form başarıyla kaydedildikten sonra kullanıcıyı yeni oluşturulan talebin detay sayfasına (/ticket/<id>/) yönlendirir.
    # Bu desen yazılım dünyasında Post/Redirect/Get (PRG) prensibi olarak bilinir ve kullanıcının F5 tuşuna basarak aynı talebi veritabanına mükerrer kaydetmesini önler.




@login_required
def ticket_edit(request, pk): 
    # pk (Primary Key): Hangi talebin düzenleneceğini belirten kimlik numarasıdır (Örn: /ticket/3/edit/ için pk=3).
    #pk: Var olan bir kaydı (bu durumda bir talebi) veritabanından benzersiz kimlik numarasına (Primary Key) göre bulup getirmek için URL'den alınan değişkendir.
    
    """
    Var olan bir destek talebini düzenleme ve durumunu güncelleme görünümü (View)
    """

    # 1. Düzenlenecek talebi ID'ye göre veritabanından çek (bulamazsa 404 dön)
    ticket = get_object_or_404(Ticket, pk=pk)
    #Güvenli Nesne Çekme: Düzenlenmek istenen talep veritabanında mevcutsa ticket değişkenine atar; mevcut değilse sunucuyu çökertmeden 404 Not Found döner.

   
    # Güvenlik Kontrolü 1: Yetkisiz kullanıcı engeli
    if not request.user.is_staff and ticket.created_by != request.user:
        messages.error(request, "Bu destek talebini düzenleme yetkiniz yok!")
        return redirect('ticket_list')


    # Güvenlik Kontrolü 2: Normal kullanıcı çözülmüş/kapatılmış talebi düzenleyemesin
    if not request.user.is_staff and ticket.status in ['resolved', 'closed']:
        messages.error(request, "Çözülmüş veya kapatılmış destek talepleri düzenlenemez!")
        return redirect('ticket_detail', pk=ticket.pk)


    if request.method == 'POST':
        # POST İsteği: Formdaki yeni verileri var olan 'ticket' nesnesinin üzerine yaz (instance=ticket)
        
        # Eski değerleri karşılaştırmak için hafızaya alıyoruz
        old_status = ticket.get_status_display()
        old_assigned = ticket.assigned_to.username if ticket.assigned_to else "Atanmadı"
        
        
        
        
        form = TicketForm(request.POST, request.FILES, instance=ticket, user=request.user)
        # request.FILES: Kullanıcının form üzerinden yüklediği dosya verilerini tutan sözlüktür.
        # request.POST: Kullanıcının form üzerinden gönderdiği metin verilerini (başlık, açıklama, kategori vb.) tutar.
        # user=request.user: Formun içine, şu an giriş yapmış olan kullanıcının bilgilerini "yazar" olarak kaydeder.
        '''
        Django standart form verilerini (başlık, açıklama vb.) request.POST içinde taşır.
        Kullanıcının bilgisayarından seçip yüklediği resim/dosya verileri ise ayrı bir paket olan request FILES içerisinde gelir. 
        Form nesnesine request.FILES parametresini vermezsek Django yüklenen dosyayı görmezden gelir ve kaydetmez.
        '''  

        # Bir form HTML sayfasıdır. Kullanıcı bu formu doldurup "Gönder" (Submit) butonuna tıkladığında,
        #  tarayıcı sayfanın URL'ine bir POST isteği gönderir.
        # Kullanıcının girdiği verileri (request.POST) alıp forma yükler.

        if form.is_valid(): # Form kurallara uygunsa (boş bırakılan zorunlu alan yoksa vb.)
            
            updated_ticket = form.save()
            # ticket = form.save(commit=False): Formdaki verilerden bir Ticket nesnesi üretir ama henüz veritabanına kaydetmez, bellekte bekletir.
        
            
            # Değişiklikleri ve yeni durumları tespit edelim (new_status önceden tanımlanıyor)
            changes = []
            new_status = updated_ticket.get_status_display() # Formdan gelen güncel durumu al
            new_assigned = updated_ticket.assigned_to.username if updated_ticket.assigned_to else "Atanmadı" # Formdan gelen güncel atanan kullanıcıyı al

            
           # CANLI BİLDİRİM: Durum değiştiyse bildirim oluştur (POST İÇİNDE)
            if old_status != new_status:
                Notification.objects.create(
                    recipient=updated_ticket.created_by,
                    actor=request.user,
                    ticket=updated_ticket,
                    message=f"#{updated_ticket.ticket_number} talebinizin durumu '{new_status}' olarak güncellendi."
                )


            
           # E-POSTA BİLDİRİMİ: Eğer durum değişmişse mail gönder
            if old_status != new_status and updated_ticket.created_by.email:
                send_notification_email(
                    subject=f"[Destek Talebi] #{updated_ticket.ticket_number} Durumu Güncellendi: {new_status}",
                    message=f"Merhaba {updated_ticket.created_by.username},\n\n#{updated_ticket.ticket_number} numaralı '{updated_ticket.title}' başlıklı talebinizin durumu '{old_status}' konumundan '{new_status}' konumuna güncellenmiştir.\n\nDetayları görüntülemek için sisteme giriş yapabilirsiniz.",
                    recipient_list=[updated_ticket.created_by.email]
                )
            if old_status != new_status:
                changes.append(f"Durum: '{old_status}' ➔ '{new_status}'")
            
            if old_assigned != new_assigned:
                changes.append(f"Atanan Yönetici: '{old_assigned}' ➔ '{new_assigned}'")
            if changes:
                for change in changes:
                    TicketActivityLog.objects.create(
                        ticket=updated_ticket,
                        actor=request.user,
                        action=change
                    )


            
           
            messages.success(request, "Destek talebi başarıyla güncellendi.")
            return redirect('ticket_detail', pk=ticket.pk)

            """
            instance=ticket (Kritik Parametre): Django'ya "Yeni bir satır oluşturma, gelen verileri bu mevcut ticket kaydının üzerine yaz" talimatını verir.

            SQL Karşılığı: Arka planda INSERT INTO yerine doğrudan UPDATE tickets_ticket SET title=..., status=... WHERE id=3; sorgusu çalışır.

            Yönlendirme: Güncelleme başarılı olduğunda kullanıcı doğrudan güncel detay sayfasına yönlendirilir (ticket_detail).
            """


    else:
        # GET İsteği: Formu var olan talebin mevcut verileriyle dolu olarak aç (instance=ticket)
        form = TicketForm(instance=ticket, user=request.user) # user=request.user eklendi
        # Formu Dolu Açma (GET): Kullanıcı sayfaya ilk girdiğinde, form kutularının içine mevcut talep verilerini (başlık, mevcut durum, kategori vb.) otomatik olarak doldurur.


    context = {
        'form': form,
        'ticket': ticket,
    }
    # Aynı ticket_form.html şablonunu tekrar kullanıyoruz!
    return render(request, 'tickets/ticket_form.html', context)

    # DRY (Don't Repeat Yourself) Prensibi: Sıfırdan yeni bir ticket_edit.html oluşturmak yerine, daha önce hazırladığımız ticket_form.html şablonunu tekrar kullanıyoruz. 
    # context içerisine ticket bilgisini de ekleyerek şablon tarafında "Yeni Talep" mi yoksa "Talebi Düzenle" mi olduğunu ayırt edebilme esnekliği sağlıyoruz.



@login_required
def ticket_delete(request, pk):
    """
    Destek talebi silme görünümü.
    GET isteğinde onay sayfasını gösterir, POST isteğinde talebi kalıcı olarak siler.
    """
    ticket = get_object_or_404(Ticket, pk=pk)

    # Güvenlik Kontrolü: Sadece yöneticiler talep silebilir
    if not request.user.is_staff:
        messages.error(request, "Destek taleplerini yalnızca yöneticiler silebilir!")
        return redirect('ticket_list')
    if request.method == 'POST':
        ticket_title = ticket.title
        ticket.delete() # veritabanından tamamen siler.
        messages.success(request, f"'{ticket_title}' başlıklı talep başarıyla silindi.")
        return redirect('ticket_list')
        
    context = {'ticket': ticket}
    return render(request, 'tickets/ticket_confirm_delete.html', context)

 



    """
    ticket = get_object_or_404(Ticket, pk=pk): Silinecek kaydı bulur.

    if request.method == 'POST': Kullanıcı onay ekranındaki "Evet, Sil" butonuna bastığında çalışır.

    ticket.delete(): İlgili talebi ve veritabanındaki CASCADE kuralı sayesinde bu talebe bağlı tüm yorumları (TicketComment) veritabanından kalıcı olarak temizler.

    ticket_confirm_delete.html: GET isteğinde kullanıcıya "Emin misiniz?" onay kartını sunar.

    """



@login_required
def profile_view(request):
    """
    Kullanıcı profil bilgilerini görüntüleme ve güncelleme ekranı.
    """
    if request.method == 'POST':

        form = UserProfileForm(request.POST, instance=request.user, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil bilgileriniz başarıyla güncellendi.")
            return redirect('profile')
        else:
            messages.error(request, "Lütfen formdaki hataları düzeltin.")
    else:
        form = UserProfileForm(instance=request.user, user=request.user)
    
    return render(request, 'tickets/profile.html', {'form': form})


@login_required
def change_password_view(request):
    """
    Güvenli Şifre Değiştirme Ekranı.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Şifre değiştiğinde kullanıcının oturumunun kapanmasını engeller:
            update_session_auth_hash(request, user)
            messages.success(request, "Şifreniz başarıyla değiştirildi!")
            return redirect('profile')
        else:
            messages.error(request, "Lütfen şifre değiştirme formundaki hataları düzeltin.")
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'tickets/change_password.html', {'form': form})



def send_notification_email(subject, message, recipient_list):
    """
    Güvenli E-posta Bildirim Gönderici Yardımcı Fonksiyonu.
    """
    if recipient_list and any(recipient_list):
        recipients = ", ".join([e for e in recipient_list if e])
        
        # Terminalde temiz ve tek bir Türkçe bildirim gösterelim:
        print("\n" + "="*60)
        print(f"📧 E-POSTA BİLDİRİMİ GÖNDERİLDİ")
        print(f"📩 Alıcı : {recipients}")
        print(f"📌 Konu  : {subject}")
        print(f"📝 İçerik:\n{message}")
        print("="*60 + "\n")
        
        try:
            # Gerçek sunucuda (SMTP) mail gönderir, geliştirme modunda konsolda tekrar basmaması için:
            from django.conf import settings
            if not settings.DEBUG:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=None,
                    recipient_list=[email for email in recipient_list if email],
                    fail_silently=True
                )
        except Exception:
            pass






@login_required
def notifications_list_view(request):
    notifications = Notification.objects.filter(recipient=request.user)
    return render(request, 'tickets/notifications.html', {'notifications': notifications})

@login_required
def mark_notification_as_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    if notification.ticket:
        return redirect('ticket_detail', pk=notification.ticket.pk)
    return redirect('notifications_list')

   