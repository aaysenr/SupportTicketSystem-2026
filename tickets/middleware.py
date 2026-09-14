from django.shortcuts import render

class CustomErrorPageMiddleware:
    """
    Geliştirme (DEBUG=True) ve üretim ortamlarında, eşleşmeyen veya 404/403 dönen
    web isteklerinin Django'nun teknik geliştirici ekranı yerine,
    kullanıcının hazırladığı şık ve güvenli hata şablonlarını (404.html, 403.html) göstermesini sağlar.
    Statik, medya, favicon ve AJAX/JSON API isteklerini bozmadan korur.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 404 ve 403 durumlarını yakala
        if response.status_code in (403, 404):
            # Statik dosya, medya ve favicon isteklerini doğrudan geçir
            if (
                request.path.startswith('/static/')
                or request.path.startswith('/media/')
                or request.path.startswith('/api/')
                or request.path == '/favicon.ico'
            ):
                return response

            # AJAX / JSON isteklerini filtrele (İstemcinin JSON ayrıştırıcısını HTML ile bozmama garantisi)
            content_type = response.get('Content-Type', '')
            if (
                content_type.startswith('application/json')
                or request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('Accept', '')
            ):
                return response

            if response.status_code == 404:
                from tickets.views import custom_404_view
                return custom_404_view(request)
            elif response.status_code == 403:
                from tickets.views import custom_403_view
                return custom_403_view(request)

        return response

