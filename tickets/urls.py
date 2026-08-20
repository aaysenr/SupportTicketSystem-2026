from django.urls import path
from . import views

urlpatterns = [
    path('', views.ticket_list, name='ticket_list'), # Ana adres / geldiğinde ticket_list görünümünü çalıştır
    path('ticket/new/', views.ticket_create, name='ticket_create'), # Yeni talep oluşturma ( /ticket/new/ )
    path('ticket/<int:pk>/', views.ticket_detail, name='ticket_detail'), # Detay adresi (Örn: /ticket/1/)
    
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
"""