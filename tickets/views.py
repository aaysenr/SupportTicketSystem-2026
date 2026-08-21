from django.shortcuts import render, get_object_or_404, redirect
from .models import Ticket
from .forms import TicketForm,CommentForm # CommentForm sınıfını detay görünümünde kullanabilmek için içeri aktarır.
from django.contrib.auth.models import User
from django.db.models import Q  # Karmaşık arama sorguları (OR işlemleri) için Q nesnesini içeri aktarıyoruz
#Q Nesnesi: Normalde Django ORM'de .filter(title=..., description=...) yazıldığında araya AND (VE) koyar. SQL'deki OR (VEYA) mantığını kurabilmek için Q nesnesini içeri aktarırız.



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
        form = UserCreationForm(request.POST)
        #UserCreationForm(request.POST): Kullanıcının girdiği kullanıcı adı ve şifre ikilisini doğrular.
        if form.is_valid():
            user = form.save()
            # user = form.save(): Yeni kullanıcıyı auth_user tablosuna şifresini hash'leyerek kaydeder.
            login(request, user)
            #login(request, user): Kayıt biter bitmez kullanıcıyı tekrar giriş formuyla uğraştırmadan otomatik olarak sisteme giriş yaptırır.
            messages.success(request, f"Hoş geldiniz {user.username}! Hesabınız başarıyla oluşturuldu.")
            #messages.success(...): Yeşil bir başarı mesajı hazırlar.
            return redirect('ticket_list') #redirect: Kayıt işlemi bittikten sonra kullanıcıyı otomatik olarak bilet listesi sayfasına yönlendirir.
        else:
            messages.error(request, "Lütfen formdaki hataları düzeltin.")
        #else: Eğer form geçerli değilse (Hata varsa)...
    else:
        form = UserCreationForm()
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
    if request.user.is_staff:
        tickets = Ticket.objects.all()
    else:
        tickets = Ticket.objects.filter(created_by=request.user)

    #request.user.is_staff: Kullanıcının yönetici / teknik destek ekibinde olup olmadığını kontrol eder.

    #filter(created_by=request.user): Standart kullanıcıya ait olmayan talepleri daha SQL seviyesinde ayıklar (WHERE created_by_id = ?). 
    # Arama ve filtreler de sadece bu daraltılmış liste üzerinde çalışır.
    
    
    # 2. URL'den gelen GET parametrelerini yakalıyoruz (Örn: /?q=yazici&status=open&priority=urgent)
    search_query = request.GET.get('q', '')
    selected_status = request.GET.get('status', '')
    selected_priority = request.GET.get('priority', '')


    #request.GET.get('anahtar', ''): Tarayıcı adres çubuğundaki parametreleri okur (Örn: /?q=yazici&status=open).
    #Eğer parametre URL'de yoksa varsayılan olarak boş metin ('') döner, hata fırlatmaz.


    # 3. Kelime Arama Filtresi (Başlıkta VEYA Açıklamada arar - icontains: büyük/küçük harf duyarsız arama)
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



    # 4. Durum Filtresi
    if selected_status:
        tickets = tickets.filter(status=selected_status)
    
    # selected_status: Eğer kullanıcı dropdown menülerden bir durum veya öncelik seçtiyse sorguya AND status = 'open' şeklinde ek filtre ekler.
    # tickets.filter(status=selected_status): Mevcut ticket listesini, sadece durumu seçilen durumla eşleşen kayıtlar kalacak şekilde günceller.
    # Eğer durum seçilmemişse bu satır atlanır ve filtreleme yapılmaz.
    #Örn: status=open ise -> WHERE status='open' sorgusu eklenir.


    # 5. Öncelik Filtresi
    if selected_priority:
        tickets = tickets.filter(priority=selected_priority)

    # selected_priority: Eğer kullanıcı dropdown menülerden bir durum veya öncelik seçtiyse sorguya AND status = 'open' şeklinde ek filtre ekler.
    # tickets.filter(priority=selected_priority): Mevcut ticket listesini, sadece önceliği seçilen öncelikle eşleşen kayıtlar kalacak şekilde günceller.
    # Eğer öncelik seçilmemişse bu satır atlanır ve filtreleme yapılmaz.
    # Örn: priority=urgent ise -> WHERE priority='urgent' sorgusu eklenir.
    
    
    
    
    
        # 6. HTML şablonuna hem filtrelenmiş verileri hem de seçili filtre durumlarını gönderiyoruz
    
    # HTML şablonuna göndereceğimiz verileri bir dictionary (sözlük) haline getiriyoruz
    context = {
        'tickets': tickets,
        'search_query': search_query,
        'selected_status': selected_status,
        'selected_priority': selected_priority,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
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
    ticket = get_object_or_404(Ticket, pk=pk)

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

    comments = ticket.comments.all()


    
    """
    Ters İlişki (Reverse Relation): models.py dosyasında TicketComment modelini yazarken ticket = ForeignKey(Ticket, related_name='comments') tanımlaması yapmıştık.

    Bu sayede ne Yapar? 
    
    Django ORM arka planda SELECT * FROM tickets_ticketcomment WHERE ticket_id = 3 ORDER BY created_at ASC sorgusunu çalıştırır 
    ve doğrudan bu talebe yazılmış yorumları kronolojik listeler.
    """
    
    
    if request.method == 'POST':
        # Yorum gönderme butonu tıklandıysa (POST isteği)
        comment_form = CommentForm(request.POST)
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
        comment_form = CommentForm()



        #Sayfaya ilk kez girildiğinde (GET), 
        #kullanıcıya sunulmak üzere boş bir CommentForm() üretilir 
        #ve context paketine eklenerek HTML şablonuna gönderilir.

    
    
    # 3. HTML şablonuna gönderilecek veri paketini hazırlınır
    context = {
        'ticket': ticket,
        'comments': comments,
        'comment_form': comment_form,
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
        form = TicketForm(request.POST)
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
            

            messages.success(request, "Destek talebiniz başarıyla oluşturuldu.") 


            # İşlem bitince oluşturulan talebin detay sayfasına yönlendir
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        # Sayfaya ilk kez girildiyse (GET isteği) boş form üret
        form = TicketForm()
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

   
    # Güvenlik Kontrolü
    if not request.user.is_staff and ticket.created_by != request.user:
        messages.error(request, "Bu destek talebini düzenleme yetkiniz yok!")
        return redirect('ticket_list')

 
    if request.method == 'POST':
        # POST İsteği: Formdaki yeni verileri var olan 'ticket' nesnesinin üzerine yaz (instance=ticket)
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save() # Var olan kaydı günceller (UPDATE sorgusu çalıştırır)
            messages.success(request, "Destek talebi başarıyla güncellendi.")
            return redirect('ticket_detail', pk=ticket.pk)

            """
            instance=ticket (Kritik Parametre): Django'ya "Yeni bir satır oluşturma, gelen verileri bu mevcut ticket kaydının üzerine yaz" talimatını verir.

            SQL Karşılığı: Arka planda INSERT INTO yerine doğrudan UPDATE tickets_ticket SET title=..., status=... WHERE id=3; sorgusu çalışır.

            Yönlendirme: Güncelleme başarılı olduğunda kullanıcı doğrudan güncel detay sayfasına yönlendirilir (ticket_detail).
            """


    else:
        # GET İsteği: Formu var olan talebin mevcut verileriyle dolu olarak aç (instance=ticket)
        form = TicketForm(instance=ticket)
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
    # Güvenlik Kontrolü
    if not request.user.is_staff and ticket.created_by != request.user:
        messages.error(request, "Bu destek talebini silme yetkiniz yok!")
        return redirect('ticket_list')
    if request.method == 'POST':
        ticket_title = ticket.title
        ticket.delete() # Veritabanından kalıcı olarak siler
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