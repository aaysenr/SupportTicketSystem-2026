from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, FileResponse, HttpResponseForbidden, Http404
import os
import mimetypes
from .models import Ticket
from .forms import TicketForm,CommentForm, UserRegisterForm # CommentForm sınıfını detay görünümünde kullanabilmek için içeri aktarır.
from django.contrib.auth.models import User
from django.db.models import Q, Count, Avg  # Karmaşık arama sorguları, sayım ve ortalama için nesneleri içeri aktarıyoruz
from django.core.paginator import Paginator  # Sayfalama (Pagination) için Paginator sınıfı
from django.core.mail import send_mail
from .models import EmailVerification
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash 
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm #
from .forms import TicketForm, CommentForm, UserRegisterForm, UserProfileForm 
from .models import Ticket, TicketComment, Category, EmailVerification, TicketActivityLog, Notification, ChatGroup, ChatMessage, UserProfile, KnowledgeBaseArticle, TicketRating

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

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # RBAC Kapsam Belirleme: Süper yönetici tüm talepleri, personel sadece kendi birimini görür
    if is_superadmin:
        base_qs = Ticket.objects.all()
        categories = Category.objects.annotate(ticket_count=Count('tickets'))
    elif profile and profile.assigned_categories.exists():
        allowed_cats = profile.assigned_categories.all()
        base_qs = Ticket.objects.filter(
            Q(category__in=allowed_cats) | Q(assigned_to=request.user)
        ).distinct()
        categories = allowed_cats.annotate(ticket_count=Count('tickets'))
    else:
        base_qs = Ticket.objects.all()
        categories = Category.objects.annotate(ticket_count=Count('tickets'))

    # 1. Temel Metrikler (Yetkili Kapsama Göre)
    total_tickets = base_qs.count()
    open_tickets = base_qs.filter(status='open').count()
    in_progress_tickets = base_qs.filter(status='in_progress').count()
    resolved_tickets = base_qs.filter(status='resolved').count()
    urgent_tickets = base_qs.filter(priority='urgent').count()

    # 2. SLA Yanıt Süresi Analizi (Geciken / Kritik Talepler)
    all_tickets_list = list(base_qs.select_related('created_by', 'category'))
    sla_breached_tickets = [t for t in all_tickets_list if t.is_sla_breached]
    sla_breached_count = len(sla_breached_tickets)

    # 3. Müşteri Memnuniyet (CSAT) Metrikleri
    csat_qs = TicketRating.objects.filter(ticket__in=base_qs)
    csat_count = csat_qs.count()
    csat_avg_raw = csat_qs.aggregate(Avg('score'))['score__avg']
    csat_avg = round(csat_avg_raw, 1) if csat_avg_raw else 0.0
    satisfied_count = csat_qs.filter(score__gte=4).count()
    satisfaction_rate = round((satisfied_count / csat_count) * 100, 1) if csat_count > 0 else 0

    # 4. Bu Ay Açılan ve Bu Ay Çözülen Talepler
    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    resolved_this_month = base_qs.filter(status='resolved', updated_at__gte=first_day_of_month).count()
    created_this_month = base_qs.filter(created_at__gte=first_day_of_month).count()

    # 5. Kategori Dağılımı Verileri (Chart.js İçin)
    category_labels = [cat.name for cat in categories]
    category_counts = [cat.ticket_count for cat in categories]

    # 6. Öncelik Dağılımı Verileri
    priority_data = {
        'Düşük': base_qs.filter(priority='low').count(),
        'Orta': base_qs.filter(priority='medium').count(),
        'Yüksek': base_qs.filter(priority='high').count(),
        'Acil': base_qs.filter(priority='urgent').count(),
    }

    context = {
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'urgent_tickets': urgent_tickets,
        'resolved_this_month': resolved_this_month,
        'created_this_month': created_this_month,
        'user_profile': profile,
        'is_superadmin': is_superadmin,
        
        # SLA & CSAT Metrikleri
        'sla_breached_count': sla_breached_count,
        'sla_breached_tickets': sla_breached_tickets[:5],
        'csat_count': csat_count,
        'csat_avg': csat_avg,
        'satisfaction_rate': satisfaction_rate,
        
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



    filter_mine = request.GET.get('mine') == '1' or request.GET.get('filter') == 'mine'
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # 1. Kullanıcının rolüne ve seçili filtreye göre temel talep kümesini belirliyoruz (RBAC)
    if request.user.is_staff or is_superadmin:
        if filter_mine:
            base_tickets = Ticket.objects.filter(created_by=request.user).select_related('created_by', 'category', 'assigned_to')
        elif is_superadmin:
            # Süper Yönetici: Sistemdeki tüm talepleri eksiksiz görür
            base_tickets = Ticket.objects.all().select_related('created_by', 'category', 'assigned_to')
        elif profile and profile.assigned_categories.exists():
            # Teknik Destek / Finans Yetkilisi: Sorumlu olduğu kategoriler + kendisine atananlar + kendi açtığı talepler
            allowed_cats = profile.assigned_categories.all()
            base_tickets = Ticket.objects.filter(
                Q(category__in=allowed_cats) | Q(assigned_to=request.user) | Q(created_by=request.user)
            ).distinct().select_related('created_by', 'category', 'assigned_to')
        else:
            base_tickets = Ticket.objects.all().select_related('created_by', 'category', 'assigned_to')
    else:
        if filter_mine:
            # "Taleplerim" Sekmesi: Sadece kendi açtığı talepler (Özel + Genel)
            base_tickets = Ticket.objects.filter(created_by=request.user).select_related('created_by', 'category', 'assigned_to')
        else:
            # "Destek Sistemi" (Genel Forum Akışı): Herkese açık tüm talepler + kullanıcının kendi talepleri
            base_tickets = Ticket.objects.filter(
                Q(is_public=True) | Q(created_by=request.user)
            ).select_related('created_by', 'category', 'assigned_to')




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
    

    # 3. URL Arama ve Filtreleme İşlemleri
    tickets = base_tickets.annotate(comment_count=Count('comments'))
    
    # URL'den gelen GET parametrelerini yakalıyoruz
    search_query = request.GET.get('q', '').strip()
    selected_status = request.GET.get('status', '').strip()
    selected_priority = request.GET.get('priority', '').strip()
    selected_sort = request.GET.get('sort', 'newest').strip()
    selected_solution = request.GET.get('solution', 'all').strip()

    # Kelime Arama Filtresi (Başlıkta VEYA Açıklamada arar)
    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Durum Filtresi
    if selected_status:
        tickets = tickets.filter(status=selected_status)

    # Öncelik Filtresi
    if selected_priority:
        tickets = tickets.filter(priority=selected_priority)

    # Çözüm Durumu Filtresi
    if selected_solution == 'solved':
        tickets = tickets.filter(Q(status='resolved') | Q(comments__is_solution=True)).distinct()
    elif selected_solution == 'unsolved':
        tickets = tickets.exclude(status='resolved').exclude(comments__is_solution=True).distinct()

    # Sıralama (Sort)
    if selected_sort == 'oldest':
        tickets = tickets.order_by('created_at')
    elif selected_sort == 'most_commented':
        tickets = tickets.order_by('-comment_count', '-created_at')
    else:  # newest
        tickets = tickets.order_by('-created_at')

    # Sayfalama (Pagination - Sayfa başına 10 talep)
    paginator = Paginator(tickets, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 4. Şablona verileri gönderiyoruz
    context = {
        'tickets': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_status': selected_status,
        'selected_priority': selected_priority,
        'selected_sort': selected_sort,
        'selected_solution': selected_solution,
        'filter_mine': filter_mine,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,

        # İstatistik Değişkenleri
        'total_count': total_count,
        'open_count': open_count,
        'in_progress_count': in_progress_count,
        'resolved_count': resolved_count,
        'urgent_count': urgent_count,
        'user_profile': profile,
        'is_superadmin': is_superadmin,
        'categories': Category.objects.all(),
        'staff_users': User.objects.filter(is_staff=True).order_by('username'),
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


    # GİZLİLİK VE RBAC KONTROLÜ:
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    if not ticket.is_public and ticket.created_by != request.user and ticket.assigned_to != request.user and not is_superadmin:
        if not request.user.is_staff:
            messages.error(request, "Bu özel destek talebini görüntüleme yetkiniz yok!")
            return redirect('ticket_list')
        elif profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                messages.error(request, "Bu departman/kategoriye ait talepleri görüntüleme yetkiniz bulunmamaktadır!")
                return redirect('ticket_list')


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

            # SLA Takibi: Destek yetkilisi yanıt verdiğinde ilk yanıt tarihini kaydet
            author_profile = getattr(comment.author, 'profile', None)
            is_staff_commenter = comment.author.is_staff or (author_profile and author_profile.is_staff_agent)
            if is_staff_commenter and not ticket.first_response_at:
                ticket.first_response_at = timezone.now()
                ticket.save(update_fields=['first_response_at'])


            
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
        'has_solution': comments.filter(is_solution=True).exists(),
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

   
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # Güvenlik Kontrolü 1: Yetkisiz kullanıcı engeli
    if not request.user.is_staff and ticket.created_by != request.user:
        messages.error(request, "Bu destek talebini düzenleme yetkiniz yok!")
        return redirect('ticket_list')

    # RBAC Kontrolü: Personel başka birimin/kategorinin talebini düzenleyemez
    if request.user.is_staff and not is_superadmin and ticket.assigned_to != request.user and ticket.created_by != request.user:
        if profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                messages.error(request, "Bu departman/kategoriye ait talepleri düzenleme yetkiniz bulunmamaktadır!")
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
    Süper yöneticiler tüm talepleri, personel ise yalnızca sorumlu olduğu departmanın taleplerini silebilir.
    GET isteğinde onay sayfasını gösterir, POST isteğinde talebi kalıcı olarak siler.
    """
    ticket = get_object_or_404(Ticket, pk=pk)

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # Güvenlik Kontrolü 1: Yalnızca yetkili personel silebilir
    if not request.user.is_staff:
        messages.error(request, "Destek taleplerini yalnızca yetkili yöneticiler silebilir!")
        return redirect('ticket_list')

    # Güvenlik Kontrolü 2: RBAC Departman İzolasyonu (Personel başka birimin talebini silemez)
    if not is_superadmin and ticket.category:
        if profile and profile.assigned_categories.exists():
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                messages.error(request, "Bu departman/kategoriye ait talepleri silme yetkiniz bulunmamaktadır!")
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
        try:
            print("\n" + "="*60)
            print(f"[E-POSTA] E-POSTA BİLDİRİMİ GÖNDERİLDİ")
            print(f"Alıcı : {recipients}")
            print(f"Konu  : {subject}")
            print(f"İçerik:\n{message}")
            print("="*60 + "\n")
        except Exception:
            pass
        
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


@login_required
def mark_all_notifications_as_read(request):
    """
    Kullanıcının tüm okunmamış bildirimlerini tek tıkla okundu olarak işaretler.
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "Tüm bildirimleriniz başarıyla okundu olarak işaretlendi.")
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'notifications_list'
    return redirect(next_url)

   

@login_required
def team_chat_view(request, chat_type='group', chat_id=None):
    """
    Yöneticiler için Ekip Sohbeti, Özel Gruplar ve DM Arayüzü.
    """
    # 🔒 Güvenlik Kontrolü: Yalnızca yöneticiler erişebilir!
    if not request.user.is_staff:
        messages.error(request, "Ekip sohbetine yalnızca yetkili yöneticiler erişebilir!")
        return redirect('ticket_list')

    # 1. Varsayılan "Genel Ekip Odası" yoksa otomatik oluştur
    general_group, _ = ChatGroup.objects.get_or_create(
        is_general=True,
        defaults={'name': 'Genel Ekip Odası', 'created_by': request.user}
    )
    if request.user not in general_group.members.all():
        general_group.members.add(request.user)

    # 2. Tüm Yöneticileri ve Üzerlerindeki Aktif Talep Sayısını Çek
    managers = User.objects.filter(is_staff=True).annotate(
        active_tickets_count=Count(
            'assigned_tickets',
            filter=Q(assigned_tickets__status__in=['open', 'in_progress'])
        )
    )

    # 3. Giriş yapan yöneticinin dahil olduğu Özel Gruplar
    user_groups = ChatGroup.objects.filter(members=request.user, is_general=False)

    # 4. Aktif Sohbet Kanalını Belirle
    active_channel = {
        'type': chat_type,
        'id': chat_id,
        'title': 'Genel Ekip Odası',
        'target_user': None,
        'group': general_group
    }

    messages_list = []

    if chat_type == 'dm' and chat_id:
        recipient = get_object_or_404(User, id=chat_id, is_staff=True)
        active_channel['title'] = f"💬 {recipient.get_full_name() or recipient.username}"
        active_channel['target_user'] = recipient
        # İki kullanıcı arasındaki özel mesajlar (DM)
        messages_list = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=recipient) |
            Q(sender=recipient, recipient=request.user)
        ).order_by('created_at')

    elif chat_type == 'group' and chat_id:
        group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
        active_channel['title'] = f"👥 {group.name}"
        active_channel['group'] = group
        messages_list = group.messages.all().order_by('created_at')

    else:
        # Varsayılan: Genel Ekip Odası
        active_channel['type'] = 'group'
        active_channel['id'] = general_group.id
        messages_list = general_group.messages.all().order_by('created_at')

    context = {
        'managers': managers,
        'general_group': general_group,
        'user_groups': user_groups,
        'active_channel': active_channel,
        'chat_messages': messages_list,
    }

    return render(request, 'tickets/team_chat.html', context)


@login_required
def send_chat_message_view(request):
    """
    Sohbet Mesajı Gönderme Endpoint'i (AJAX & Form Uyumlu)
    """
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Yetkisiz erişim'}, status=403)

    if request.method == 'POST':
        chat_type = request.POST.get('chat_type')
        chat_id = request.POST.get('chat_id')
        content = request.POST.get('content', '').strip()

        if not content:
            return JsonResponse({'status': 'error', 'message': 'Mesaj boş olamaz'}, status=400)

        msg = None
        if chat_type == 'dm':
            recipient = get_object_or_404(User, id=chat_id, is_staff=True)
            msg = ChatMessage.objects.create(sender=request.user, recipient=recipient, content=content)
        else:
            group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
            msg = ChatMessage.objects.create(sender=request.user, group=group, content=content)

        # WebSocket kullanıcılarına anlık yayınla (Channel Layer Broadcast)
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                if chat_type == 'dm':
                    u1, u2 = sorted([request.user.id, recipient.id])
                    room_group = f"chat_dm_{u1}_{u2}"
                else:
                    room_group = f"chat_group_{group.id}"
                
                async_to_sync(channel_layer.group_send)(
                    room_group,
                    {
                        "type": "chat_message_broadcast",
                        "message_id": msg.id,
                        "sender_id": msg.sender.id,
                        "sender_name": msg.sender.get_full_name() or msg.sender.username,
                        "content": msg.content,
                        "created_at": msg.created_at.strftime('%H:%M')
                    }
                )
        except Exception:
            pass

        return JsonResponse({
            'status': 'success',
            'message_id': msg.id,
            'sender_id': msg.sender.id,
            'sender_name': msg.sender.get_full_name() or msg.sender.username,
            'content': msg.content,
            'created_at': msg.created_at.strftime('%H:%M')
        })

    return JsonResponse({'status': 'error', 'message': 'Geçersiz istek'}, status=400)


@login_required
def create_chat_group_view(request):
    """
    Yeni Özel Sohbet Grubu Oluşturma
    """
    if not request.user.is_staff:
        messages.error(request, "Yetkiniz yok!")
        return redirect('ticket_list')

    if request.method == 'POST':
        group_name = request.POST.get('group_name', '').strip()
        member_ids = request.POST.getlist('members')

        if group_name:
            group = ChatGroup.objects.create(name=group_name, created_by=request.user)
            # Kurucuyu gruba ekle
            group.members.add(request.user)
            # Seçilen diğer yöneticileri ekle
            if member_ids:
                selected_members = User.objects.filter(id__in=member_ids, is_staff=True)
                group.members.add(*selected_members)

            messages.success(request, f"'{group_name}' sohbet grubu oluşturuldu.")
            return redirect('team_chat_detail', chat_type='group', chat_id=group.id)

    return redirect('team_chat')


@login_required
def get_chat_messages_api(request, chat_type, chat_id):
    """
    Canlı Sohbet Yenileme İçin Mesajları JSON Dönen API.
    ?after_id=<id> parametresi verildiğinde yalnızca o ID'den sonraki yeni mesajları döner.
    """
    if not request.user.is_staff:
        return JsonResponse({'messages': []}, status=403)

    after_id = request.GET.get('after_id')

    if chat_type == 'dm':
        recipient = get_object_or_404(User, id=chat_id, is_staff=True)
        messages_qs = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=recipient) |
            Q(sender=recipient, recipient=request.user)
        )
    else:
        group = get_object_or_404(ChatGroup, id=chat_id, members=request.user)
        messages_qs = group.messages.all()

    if after_id and after_id.isdigit():
        messages_qs = messages_qs.filter(id__gt=int(after_id))

    messages_qs = messages_qs.order_by('created_at')

    data = []
    for m in messages_qs:
        data.append({
            'message_id': m.id,
            'sender_id': m.sender.id,
            'sender_name': m.sender.get_full_name() or m.sender.username,
            'content': m.content,
            'created_at': m.created_at.strftime('%H:%M')
        })

    return JsonResponse({'messages': data})


@login_required
def toggle_comment_solution(request, comment_id):
    """
    Bir yorumu En İyi Yanıt / Çözüm olarak işaretler veya işaretini kaldırır.
    İzin: Sadece talebi açan kullanıcı veya yöneticiler (is_staff) işlem yapabilir.
    AJAX / Fetch API ile sayfa yenilenmeden çalışmayı destekler.
    """
    comment = get_object_or_404(TicketComment, id=comment_id)
    ticket = comment.ticket
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.GET.get('ajax') == '1'

    # Yetki kontrolü: Yalnızca talebi açan veya yönetici işaretleyebilir
    if request.user != ticket.created_by and not request.user.is_staff:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Bu yorumu çözüm olarak işaretleme yetkiniz yok.'}, status=403)
        messages.error(request, "Bu yorumu çözüm olarak işaretleme yetkiniz yok.")
        return redirect('ticket_detail', pk=ticket.id)

    if comment.is_solution:
        comment.is_solution = False
        comment.save()
        msg = "Çözüm işareti kaldırıldı."
        # Geri alma: Başka çözüm yoksa ve talep çözüldü durumundaysa devam ediyor durumuna geri çek
        if ticket.status == 'resolved' and not ticket.comments.filter(is_solution=True).exists():
            ticket.status = 'in_progress'
            ticket.save(update_fields=['status', 'updated_at'])
            TicketActivityLog.objects.create(
                ticket=ticket,
                actor=request.user,
                action=f"Yorum (#{comment.id}) çözüm işareti geri alındı; talep 'Devam Ediyor' olarak güncellendi."
            )
        if not is_ajax:
            messages.info(request, msg)
    else:
        # Talebe ait tüm yorumların çözüm durumunu sıfırla (Her talepte tek onaylı çözüm)
        ticket.comments.update(is_solution=False)
        comment.is_solution = True
        comment.save()
        # Talebi otomatik olarak 'Çözüldü' yap
        if ticket.status != 'resolved':
            ticket.status = 'resolved'
            ticket.save(update_fields=['status', 'updated_at'])
            TicketActivityLog.objects.create(
                ticket=ticket,
                actor=request.user,
                action=f"Yorum (#{comment.id}) çözüm olarak onaylandı; talep 'Çözüldü' olarak işaretlendi."
            )
        msg = "Yorum 'En İyi Yanıt / Çözüm' olarak işaretlendi! ✅"
        if not is_ajax:
            messages.success(request, msg)

    has_solution = ticket.comments.filter(is_solution=True).exists()

    if is_ajax:
        return JsonResponse({
            'status': 'ok',
            'is_solution': comment.is_solution,
            'comment_id': comment.id,
            'has_solution': has_solution,
            'ticket_status': ticket.status,
            'ticket_status_display': ticket.get_status_display(),
            'message': msg
        })

    return redirect('ticket_detail', pk=ticket.id)


@login_required
def toggle_comment_like(request, comment_id):
    """
    Bir yorumu faydalı bulup beğenmeyi (upvote) veya beğeniyi kaldırmayı sağlar.
    AJAX / Fetch API ile sayfa yenilenmeden çalışmayı destekler.
    """
    comment = get_object_or_404(TicketComment, id=comment_id)
    ticket = comment.ticket
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.GET.get('ajax') == '1'

    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
        liked = False
        msg = "Yorum beğenisi kaldırıldı."
        if not is_ajax:
            messages.info(request, msg)
    else:
        comment.likes.add(request.user)
        liked = True
        msg = "Yorumu faydalı buldunuz! 👍"
        if not is_ajax:
            messages.success(request, msg)

    if is_ajax:
        return JsonResponse({
            'status': 'ok',
            'liked': liked,
            'like_count': comment.like_count,
            'comment_id': comment.id,
            'message': msg
        })

    return redirect('ticket_detail', pk=ticket.id)


# --- BİLGİ BANKASI (KNOWLEDGE BASE / FAQ) GÖRÜNÜMLERİ ---

def knowledge_base_list_view(request):
    """
    Sıkça sorulan sorular (SSS) ve Bilgi Bankası makale listesi.
    """
    q = request.GET.get('q', '').strip()
    selected_category = request.GET.get('category', '').strip()

    articles = KnowledgeBaseArticle.objects.filter(is_published=True)

    if q:
        articles = articles.filter(
            Q(title__icontains=q) | 
            Q(content__icontains=q) | 
            Q(keywords__icontains=q)
        )

    if selected_category:
        articles = articles.filter(category=selected_category)

    # Kategori istatistikleri
    categories_stats = []
    for cat_code, cat_name in KnowledgeBaseArticle.CATEGORY_CHOICES:
        count = KnowledgeBaseArticle.objects.filter(is_published=True, category=cat_code).count()
        categories_stats.append({
            'code': cat_code,
            'name': cat_name,
            'count': count,
        })

    paginator = Paginator(articles, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'articles': page_obj,
        'categories_stats': categories_stats,
        'search_query': q,
        'selected_category': selected_category,
        'category_choices': KnowledgeBaseArticle.CATEGORY_CHOICES,
    }
    return render(request, 'tickets/knowledge_base.html', context)


def knowledge_base_detail_view(request, pk):
    """
    Tek bir Bilgi Bankası makalesinin detay sayfası.
    """
    article = get_object_or_404(KnowledgeBaseArticle, pk=pk, is_published=True)
    # Görüntülenme sayacını artır
    KnowledgeBaseArticle.objects.filter(pk=pk).update(views_count=article.views_count + 1)
    article.refresh_from_db(fields=['views_count'])

    # Benzer / İlgili makaleler
    related_articles = KnowledgeBaseArticle.objects.filter(
        is_published=True, category=article.category
    ).exclude(pk=article.pk)[:4]

    context = {
        'article': article,
        'related_articles': related_articles,
    }
    return render(request, 'tickets/knowledge_base_detail.html', context)


def kb_suggest_api(request):
    """
    Yeni talep formunda kullanıcının yazdığı başlığa göre canlı SSS ve benzer çözülmüş talep önerisi sunan AJAX API'si.
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 3:
        return JsonResponse({'suggestions': []})

    suggestions = []

    # 1. Bilgi Bankası Makaleleri
    kb_qs = KnowledgeBaseArticle.objects.filter(
        is_published=True
    ).filter(
        Q(title__icontains=q) | Q(keywords__icontains=q) | Q(content__icontains=q)
    )[:4]

    for item in kb_qs:
        suggestions.append({
            'id': item.id,
            'title': item.title,
            'category': item.get_category_display(),
            'snippet': (item.content[:120] + '...') if len(item.content) > 120 else item.content,
            'url': f"/knowledge-base/{item.id}/",
            'type': 'kb',
            'type_display': '📚 Bilgi Bankası Makalesi'
        })

    # 2. Herkese Açık ve Çözülmüş Benzer Talepler
    resolved_tickets = Ticket.objects.filter(
        is_public=True,
        status='resolved'
    ).filter(
        Q(title__icontains=q) | Q(description__icontains=q)
    ).select_related('category')[:3]

    for t in resolved_tickets:
        suggestions.append({
            'id': t.id,
            'title': t.title,
            'category': t.category.name if t.category else "Genel",
            'snippet': (t.description[:120] + '...') if len(t.description) > 120 else t.description,
            'url': f"/ticket/{t.id}/",
            'type': 'ticket',
            'type_display': '✅ Çözülmüş Topluluk Talebi'
        })

    return JsonResponse({'suggestions': suggestions})


@login_required
def submit_ticket_rating_api(request, ticket_id):
    """
    Çözülmüş bir destek talebi için müşteri memnuniyeti (CSAT) puanı ve görüşü kaydetme API'si.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Sadece POST isteği kabul edilir.'}, status=405)

    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Sadece talep sahibi veya süper yönetici değerlendirebilir
    if ticket.created_by != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Yalnızca talep sahibi değerlendirme yapabilir.'}, status=403)

    if ticket.status != 'resolved':
        return JsonResponse({'status': 'error', 'message': 'Sadece çözüldü durumundaki talepler değerlendirilebilir.'}, status=400)

    try:
        score = int(request.POST.get('score', 5))
        if score < 1 or score > 5:
            score = 5
    except (ValueError, TypeError):
        score = 5

    feedback = request.POST.get('feedback', '').strip()

    rating, created = TicketRating.objects.update_or_create(
        ticket=ticket,
        defaults={
            'user': request.user,
            'score': score,
            'feedback': feedback,
        }
    )

    return JsonResponse({
        'status': 'ok',
        'score': rating.score,
        'feedback': rating.feedback,
        'message': 'Geri bildiriminiz ve puanınız başarıyla kaydedildi. Teşekkür ederiz! ⭐'
    })


# --- GÜVENLİ DOSYA İNDİRME VE AKIŞ GÖRÜNÜMLERİ (SECURE ATTACHMENTS) ---

@login_required
def download_ticket_attachment(request, pk):
    """
    Talebe eklenen dosyayı yetki kontrolü yaparak güvenli bir şekilde sunar veya indirir.
    Gizli taleplerin doğrudan medya URL'si üzerinden yetkisiz indirilmesini engeller.
    """
    ticket = get_object_or_404(Ticket, pk=pk)

    if not ticket.attachment:
        raise Http404("Bu talebe ait ek dosya bulunamadı.")

    # Gizlilik ve RBAC Kontrolü
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    if not ticket.is_public and ticket.created_by != request.user and ticket.assigned_to != request.user and not is_superadmin:
        if not request.user.is_staff:
            return HttpResponseForbidden("Bu özel talebin ek dosyasını görüntüleme yetkiniz bulunmamaktadır.")
        elif profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                return HttpResponseForbidden("Bu departman/kategoriye ait ek dosyayı indirme yetkiniz bulunmamaktadır.")

    try:
        file_path = ticket.attachment.path
        if not os.path.exists(file_path):
            raise Http404("Dosya sunucu diskinde bulunamadı.")
    except (ValueError, NotImplementedError):
        file_path = None

    filename = ticket.attachment_filename or os.path.basename(ticket.attachment.name)
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or 'application/octet-stream'

    # Resim veya PDF ise tarayıcı içinde önizle (inline), download=1 veya diğer formatlarda indir (attachment)
    is_previewable = content_type.startswith('image/') or content_type == 'application/pdf'
    force_download = request.GET.get('download') == '1'
    as_attachment = force_download or (not is_previewable)

    if file_path:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type, as_attachment=as_attachment, filename=filename)
    else:
        response = FileResponse(ticket.attachment.open('rb'), content_type=content_type, as_attachment=as_attachment, filename=filename)

    return response


@login_required
def download_comment_attachment(request, comment_id):
    """
    Yorumlara eklenen dosyayı yetki kontrolü yaparak güvenli bir şekilde sunar veya indirir.
    İç notlara (is_internal) ait dosyaların normal kullanıcılarca erişilmesini engeller.
    """
    comment = get_object_or_404(TicketComment, id=comment_id)
    ticket = comment.ticket

    if not comment.attachment:
        raise Http404("Bu yoruma ait ek dosya bulunamadı.")

    # İç not eki kontrolü: Yalnızca yetkililer görebilir
    if comment.is_internal and not request.user.is_staff:
        return HttpResponseForbidden("Yöneticilere özel iç not dosyalarına erişim yetkiniz bulunmamaktadır.")

    # Talep Gizlilik ve RBAC Kontrolü
    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    if not ticket.is_public and ticket.created_by != request.user and ticket.assigned_to != request.user and not is_superadmin:
        if not request.user.is_staff:
            return HttpResponseForbidden("Bu özel talebin yorum ekini görüntüleme yetkiniz bulunmamaktadır.")
        elif profile and profile.assigned_categories.exists() and ticket.category:
            if not profile.assigned_categories.filter(id=ticket.category.id).exists():
                return HttpResponseForbidden("Bu departman/kategoriye ait yorum ekini indirme yetkiniz bulunmamaktadır.")

    try:
        file_path = comment.attachment.path
        if not os.path.exists(file_path):
            raise Http404("Dosya sunucu diskinde bulunamadı.")
    except (ValueError, NotImplementedError):
        file_path = None

    filename = comment.attachment_filename or os.path.basename(comment.attachment.name)
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or 'application/octet-stream'

    is_previewable = content_type.startswith('image/') or content_type == 'application/pdf'
    force_download = request.GET.get('download') == '1'
    as_attachment = force_download or (not is_previewable)

    if file_path:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type, as_attachment=as_attachment, filename=filename)
    else:
        response = FileResponse(comment.attachment.open('rb'), content_type=content_type, as_attachment=as_attachment, filename=filename)

    return response


# --- RAPOR DIŞA AKTARMA (EXCEL / CSV EXPORT) ---

import csv
from django.http import HttpResponse

@login_required
def export_tickets_csv(request):
    """
    Destek taleplerini Excel uyumlu CSV (UTF-8 BOM ve ';' ayracı) formatında dışa aktarır.
    Aktif filtreleri ve RBAC departman yetkilendirmesini uygular.
    """
    if not request.user.is_staff:
        messages.error(request, "Rapor dışa aktarma yetkiniz bulunmamaktadır!")
        return redirect('ticket_list')

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # 1. RBAC Kapsamı
    if is_superadmin:
        base_qs = Ticket.objects.all()
    elif profile and profile.assigned_categories.exists():
        allowed_cats = profile.assigned_categories.all()
        base_qs = Ticket.objects.filter(
            Q(category__in=allowed_cats) | Q(assigned_to=request.user)
        ).distinct()
    else:
        base_qs = Ticket.objects.all()

    # 2. Filtre Parametreleri
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    priority = request.GET.get('priority', '').strip()
    category_id = request.GET.get('category', '').strip()
    mine = request.GET.get('mine') == '1'

    tickets = base_qs
    if q:
        tickets = tickets.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if status:
        tickets = tickets.filter(status=status)
    if priority:
        tickets = tickets.filter(priority=priority)
    if category_id:
        tickets = tickets.filter(category_id=category_id)
    if mine:
        tickets = tickets.filter(created_by=request.user)

    tickets = tickets.select_related('created_by', 'category', 'assigned_to').prefetch_related('comments').order_by('-created_at')

    # 3. CSV Yanıtı (Windows Excel Türkçe karakter uyumu için utf-8-sig ve ';' ayracı)
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"destek_talepleri_raporu_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Talep No', 'Başlık', 'Kategori', 'Öncelik', 'Durum',
        'Oluşturan', 'Atanan Yönetici', 'Gizlilik', 'Oluşturulma Tarihi',
        'Son Güncelleme', 'İlk Yanıt Tarihi', 'SLA Durumu', 'Yorum Sayısı'
    ])

    for t in tickets:
        sla_text = "SLA Aşıldı" if t.is_sla_breached else ("İlk Yanıt Verildi" if t.first_response_at else "Zamanında Devam Ediyor")
        writer.writerow([
            t.ticket_number,
            t.title,
            t.category.name if t.category else "Kategorisiz",
            t.get_priority_display(),
            t.get_status_display(),
            t.created_by.username,
            t.assigned_to.username if t.assigned_to else "Atanmadı",
            "Herkese Açık" if t.is_public else "Özel / Gizli",
            t.created_at.strftime('%d.%m.%Y %H:%M') if t.created_at else "",
            t.updated_at.strftime('%d.%m.%Y %H:%M') if t.updated_at else "",
            t.first_response_at.strftime('%d.%m.%Y %H:%M') if t.first_response_at else "Henüz Yanıtlanmadı",
            sla_text,
            t.comments.count()
        ])

    return response


# --- TOPLU İŞLEMLER (BULK ACTIONS) ---

@login_required
def bulk_ticket_action(request):
    """
    Talep listesinde seçilen birden fazla talep üzerinde toplu işlem uygular (Durum Değiştirme, Atama, Kategori).
    """
    if request.method != 'POST':
        return redirect('ticket_list')

    if not request.user.is_staff:
        messages.error(request, "Toplu işlem yapma yetkiniz bulunmamaktadır!")
        return redirect('ticket_list')

    selected_ids = request.POST.getlist('selected_tickets')
    action = request.POST.get('bulk_action', '').strip()
    target_value = request.POST.get('bulk_target_value', '').strip()

    if not selected_ids:
        messages.warning(request, "Lütfen işlem uygulamak için en az bir talep seçiniz.")
        return redirect('ticket_list')

    profile = getattr(request.user, 'profile', None)
    is_superadmin = request.user.is_superuser or (profile and profile.role == 'superadmin')

    # Yetkili olunan talepleri filtrele
    tickets = Ticket.objects.filter(id__in=selected_ids)
    if not is_superadmin and profile and profile.assigned_categories.exists():
        tickets = tickets.filter(
            Q(category__in=profile.assigned_categories.all()) | Q(assigned_to=request.user)
        )

    updated_count = 0

    if action == 'status':
        valid_statuses = dict(Ticket.STATUS_CHOICES).keys()
        if target_value in valid_statuses:
            for t in tickets:
                old_status = t.get_status_display()
                t.status = target_value
                t.save(update_fields=['status', 'updated_at'])
                TicketActivityLog.objects.create(
                    ticket=t,
                    actor=request.user,
                    action=f"Toplu İşlem: Durum '{old_status}' ➔ '{t.get_status_display()}' olarak güncellendi."
                )
                updated_count += 1
            messages.success(request, f"{updated_count} adet talebin durumu başarıyla güncellendi.")
        else:
            messages.error(request, "Geçersiz durum seçimi.")

    elif action == 'assign':
        if target_value == 'unassign':
            for t in tickets:
                t.assigned_to = None
                t.save(update_fields=['assigned_to', 'updated_at'])
                TicketActivityLog.objects.create(
                    ticket=t,
                    actor=request.user,
                    action="Toplu İşlem: Atanan yönetici kaldırıldı."
                )
                updated_count += 1
            messages.success(request, f"{updated_count} adet talebin ataması kaldırıldı.")
        else:
            try:
                assignee = User.objects.get(id=int(target_value), is_staff=True)
                for t in tickets:
                    t.assigned_to = assignee
                    t.save(update_fields=['assigned_to', 'updated_at'])
                    TicketActivityLog.objects.create(
                        ticket=t,
                        actor=request.user,
                        action=f"Toplu İşlem: Talep {assignee.username} yöneticisine atandı."
                    )
                    updated_count += 1
                messages.success(request, f"{updated_count} adet talep {assignee.username} yöneticisine atandı.")
            except (ValueError, User.DoesNotExist):
                messages.error(request, "Seçilen yönetici bulunamadı.")

    elif action == 'category':
        try:
            new_cat = Category.objects.get(id=int(target_value))
            for t in tickets:
                old_cat_name = t.category.name if t.category else "Kategorisiz"
                t.category = new_cat
                t.save(update_fields=['category', 'updated_at'])
                TicketActivityLog.objects.create(
                    ticket=t,
                    actor=request.user,
                    action=f"Toplu İşlem: Kategori '{old_cat_name}' ➔ '{new_cat.name}' olarak değiştirildi."
                )
                updated_count += 1
            messages.success(request, f"{updated_count} adet talebin kategorisi güncellendi.")
        except (ValueError, Category.DoesNotExist):
            messages.error(request, "Seçilen kategori bulunamadı.")
    else:
        messages.warning(request, "Geçersiz işlem seçildi.")

    return redirect('ticket_list')

