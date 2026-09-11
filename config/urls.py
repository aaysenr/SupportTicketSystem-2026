"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""



from django.contrib import admin
from django.urls import path, include  
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from tickets import views as ticket_views


# GÜVENLİK KURALI: Admin paneline SADECE Süper Kullanıcılar (is_superuser=True) girebilsin!
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser
urlpatterns = [
    # Kullanıcı /admin/ girdiğinde 404 almasın, doğrudan /super-admin/ adresine yönlensin
    path('admin/', RedirectView.as_view(url='/super-admin/', permanent=False)),
    path('super-admin/', admin.site.urls),
    
    # Hata Sayfaları Doğrudan Canlı Önizleme Rotaları (DEBUG açıkken de incelenebilir)
    path('404/', ticket_views.custom_404_view, name='preview_404'),
    path('403/', ticket_views.custom_403_view, name='preview_403'),
    path('500/', ticket_views.custom_500_view, name='preview_500'),

    path('', include('tickets.urls')), # Ana uygulama bağlantısı
    path('captcha/', include('captcha.urls')), 
]

# Canlıda (DEBUG=False) otomatik devreye giren özel hata yöneticileri
handler404 = 'tickets.views.custom_404_view'
handler403 = 'tickets.views.custom_403_view'
handler500 = 'tickets.views.custom_500_view'


"""
from django.urls import path, include: Başka bir URL dosyasını ana haritaya bağlamamızı sağlayan include modülünü içe aktarır.

path('', include('tickets.urls')):
Kullanıcı ana adrese ([http://127.0.0.1:8000/](http://127.0.0.1:8000/)) geldiğinde,
homepage direkt tickets list sayfasına yonlendirir.
"""

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

'''
Geliştirme ortamında (DEBUG ortamında) yüklenen resim ve dosyaların web tarayıcısında açılabilmesini sağlar.
'''