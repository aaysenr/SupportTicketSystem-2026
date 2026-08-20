from django.shortcuts import render, get_object_or_404, redirect
from .models import Ticket
from .forms import TicketForm,CommentForm # CommentForm sınıfını detay görünümünde kullanabilmek için içeri aktarır.
from django.contrib.auth.models import User

# render: Django'nun HTML şablonlarını (template) verilerle birleştirip kullanıcıya sunmasını sağlayan pratik bir yardımcı fonksiyondur.
# from .models import Ticket: Bulunduğumuz uygulama klasöründeki (.) models.py dosyasından veritabanı tablomuzu temsil eden Ticket modelini projeye dahil eder.
#get_object_or_404: Veritabanından nesne çekerken hata yönetimini (Exception Handling) otomatik yapan kısayoldur.

# redirect: Kullanıcıyı bir işlem bittikten sonra başka bir URL'e yönlendiren fonksiyondur. Sayfanın yenilenmesiyle formun mükerrer (çift) gönderilmesini engeller.

# from .forms import TicketForm: TicketForm sınıfını kullanabilmek için içeri alır.

# from django.contrib.auth.models import User: Oturum açmamış test durumlarında kullanıcı atayabilmek için Django'nun kullanıcı modelini içeri aktarır.



def ticket_list(request):

    # Django'da bir sayfa istendiğinde çalışacak fonksiyon tanımlanır.

    # request: Tarayıcıdan gelen HTTP isteğine dair tüm bilgileri (kullanıcı oturumu, ip adresi, form verileri vb.) taşıyan zorunlu parametredir.
    
    """
    Tüm destek taleplerini veritabanından çekip listeleyen görünüm (View)
    """
    # Django ORM (Object-Relational Mapper) kullanarak veritabanından tüm ticket kayıtlarını sorguluyoruz.
    # Veritabanından tüm talepleri oluşturulma tarihine göre (models.py'daki ordering kuralıyla) çekiyoruz
    
    tickets = Ticket.objects.all()
    #Django'nun ORM (Object-Relational Mapper) yapısını kullanarak SQL komutu yazmadan veritabanındaki tüm biletleri (tickets) çekeriz.
    # Arka planda SELECT * FROM tickets_ticket; sorgusu çalıştırılır.
    # Eğer models.py dosyanızda ordering tanımlandıysa (örneğin en yeni bilet en üstte olacak şekilde), veriler bu sıraya göre tickets değişkenine atanır.

    # HTML şablonuna göndereceğimiz verileri bir dictionary (sözlük) haline getiriyoruz
    context = {
        'tickets': tickets
    }
    # Veritabanından çekilen veriyi HTML şablonuna aktarabilmek için bir Python dictionary (sözlük) yapısı oluşturulur.
    # Sözlükteki 'tickets' anahtarı, HTML tarafında bu verilere erişmek için kullanacağımız değişken adı olacaktır.

    # Şablonu ve veriyi birleştirip kullanıcıya HTML yanıtı dönüyoruz
    return render(request, 'tickets/ticket_list.html', context)

    #render fonksiyonu 3 temel bileşeni bir araya getirir:
    #request: Kullanıcı isteği.
    #tickets/ticket_list.html: Verilerin basılacağı HTML şablonunun yolu.
    #context: Şablona gönderilecek veri paketi.
    #Bu işlem sonucunda Django dinamik olarak HTML içeriğini üretir ve tarayıcıya yanıt olarak gönderir.
    #Çalışma Mantığı Özeti:
    #Tarayıcı İsteği ➔ ticket_list (View) ➔ Ticket.objects.all() (Veritabanı) ➔ context (Veri Paketleme) ➔ ticket_list.html (Render) ➔ Kullanıcıya Gösterim



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






    # 2. İlgili talebe yapılan yorumları çekme:
    # models.py dosyamızda TicketComment modelindeki 'ticket' alanına related_name='comments' vermiştik.
    # Bu sayede 'ticket.comments.all()' diyerek o talebe ait tüm yorumları tarihe göre çekebiliriz.
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
            




            # Yorumu yazan kullanıcıyı atayalım
            if request.user.is_authenticated:
                comment.author = request.user
            else:
                comment.author = User.objects.first()
                
            # Artık tam kaydı veritabanına yazalım
            comment.save()


            #comment.author: Yorumu yazan kişiyi (author) oturum açmış kullanıcı olarak atar (oturum yoksa geliştirme ortamında ilk kullanıcıyı atar).

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
            

            # Oluşturan kullanıcıyı atayalım:
            if request.user.is_authenticated:
                ticket.created_by = request.user
                #Bir kullanıcı giriş yapmışsa (is_authenticated True), o kullanıcının bilgilerini alıp modeldeki created_by alanına atar.
                # ticket.created_by = request.user: Eksik kalan "oluşturan kullanıcı" bilgisini arkadan sisteme giriş yapmış olan kullanıcı olarak atar.
            else:
                # Oturum açılmamışsa test kolaylığı için veritabanındaki ilk kullanıcıyı atayalım
                ticket.created_by = User.objects.first()
                
            # Şimdi veritabanına tam kaydı gerçekleştirebiliriz
            ticket.save()
            #ticket.save(): Nesne artık eksiksiz olduğu için veritabanına nihai kaydı (INSERT INTO) gerçekleştirir.
            
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
