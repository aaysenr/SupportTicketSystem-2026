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


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tickets.urls')), # <-- Ana adrese bağladık
    path('captcha/', include('captcha.urls')), 
]

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