from django.urls import path
from . import views

urlpatterns = [
    # Talep İşlemleri
    path('', views.ticket_list, name='ticket_list'), # Ana adres / geldiğinde ticket_list görünümünü çalıştır
    path('ticket/new/', views.ticket_create, name='ticket_create'), # Yeni talep oluşturma ( /ticket/new/ )
    path('ticket/<int:pk>/', views.ticket_detail, name='ticket_detail'), # Detay adresi (Örn: /ticket/1/)
    path('ticket/<int:pk>/edit/', views.ticket_edit, name='ticket_edit'), # Talep düzenleme adresi
    path('ticket/<int:pk>/delete/', views.ticket_delete, name='ticket_delete'),
    # Profil ve Şifre İşlemleri
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.change_password_view, name='change_password'),


    # Kullanıcı Kimlik Doğrulama (Auth) İşlemleri
    path('register/', views.register_user, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('dashboard/', views.admin_dashboard_view, name='admin_dashboard'), # Yönetici Dashboard'u
    path('notifications/', views.notifications_list_view, name='notifications_list'),
    path('notifications/<int:pk>/read/', views.mark_notification_as_read, name='mark_notification_read'),




]


"""
from django.urls import path: Django'nun URL kalıplarını tanımlayan path fonksiyonunu içeri aktarır.

from . import views: Bulunduğumuz klasördeki (.) views.py dosyasını projeye dahil eder ki oradaki fonksiyonlara erişebilelim.

path('', views.ticket_list, name='ticket_list'):

'' (Boş Tırnak): Kök dizini (ana adresi) temsil eder.

views.ticket_list: Bu adrese girildiğinde views.py içindeki ticket_list fonksiyonunu tetikler.

name='ticket_list': Bu adrese verilen özel koddur/takma addır. 

İleride HTML içinde veya Python kodunda adresi elle (/) yazmak yerine {% url 'ticket_list' %} diyerek 
dinamik olarak çağırabilmemizi sağlar.


path('ticket/<int:pk>/', views.ticket_detail, name='ticket_detail'):
ticket/<int:pk>/: Dinamik URL yapısıdır. URL'deki sayıyı yakalar.
views.ticket_detail: Gelen sayıyı pk parametresi olarak alıp bu fonksiyonu tetikler.
name='ticket_detail': Bu URL kuralına verilen takma isimdir. HTML şablonlarında {% url 'ticket_detail' ticket.id %} şeklinde dinamik link oluşturmamızı sağlar.




path('ticket/new/', views.ticket_create, name='ticket_create'): 
Tarayıcıdan [http://127.0.0.1:8000/ticket/new/](http://127.0.0.1:8000/ticket/new/) 
adresine bir istek geldiğinde, views.py içerisindeki ticket_create fonksiyonunu tetikler.
 name='ticket_create' takma adı sayesinde HTML şablonlarında {% url 'ticket_create' %} yazarak bu sayfaya dinamik link verebiliriz.



path('ticket/<int:pk>/edit/', views.ticket_edit, name='ticket_edit'):

Tarayıcıdan gelen [http://127.0.0.1:8000/ticket/1/edit/](http://127.0.0.1:8000/ticket/1/edit/) gibi istekleri karşılar.

<int:pk> parçası düzenlenecek talebin ID numarasını yakalar ve views.py içerisindeki ticket_edit(request, pk) fonksiyonuna aktarır.

name='ticket_edit' takma adı sayesinde HTML şablonlarında {% url 'ticket_edit' ticket.id %} yazarak düzenleme sayfasına dinamik bağlantı vermeyi sağlar.



URL Yapısının Sıralama Mantığı:

ticket/new/: Sabit metin kuralı en üstte yer alır.

ticket/<int:pk>/: Sadece sayısal ID içeren detay sayfalarını yakalar.

ticket/<int:pk>/edit/: Sayısal ID ve ardından gelen /edit/ son ekini yakalayarak düzenleme ekranına yönlendirir. Çakışma olmadan her üç adres de bağımsız çalışır.



# AUTH KISMI:
path('register/', ... name='register'):

Tarayıcıdan /register/ adresine gidildiğinde views.register_user çalışır ve register.html formunu ekrana basar.

Şablonlarda {% url 'register' %} yazılarak dinamik link verilir.

path('login/', ... name='login'):

/login/ adresi views.login_user görünümünü tetikler. Kullanıcı adı ve şifre doğrulanır.

@login_required ile kilitli bir sayfaya yetkisiz girildiğinde veya çıkış yapıldığında kullanıcı buraya yönlendirilir.

path('logout/', ... name='logout'):

/logout/ adresi oturumu sonlandırıp kullanıcıyı tekrar login ekranına atar




Dinamik Parametre (<int:pk>): URL'deki sayısal ID'yi yakalar (Örn: /ticket/4/delete/ için pk=4) ve views.ticket_delete(request, pk) fonksiyonuna iletir.
İsimlendirme:
 (name='ticket_delete'): Şablonlarda {% url 'ticket_delete' ticket.id %} şeklinde temiz, dinamik bağlantılar oluşturmayı sağlar.
 URL Sıralama Mantığı:
 ticket/new/ ---- Statik kural
 ticket/<int:pk>/ ----- Detay kuralı
 ticket/<int:pk>/edit/ ----- Düzenleme kuralı
 ticket/<int:pk>/delete/ ------- Silme onay kuralı


"""