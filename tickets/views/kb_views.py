from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from django.db.models import Q, Count, F
from django.core.paginator import Paginator

from ..models import KnowledgeBaseArticle, Category, Ticket


def knowledge_base_list_view(request):
    """
    Sıkça sorulan sorular (SSS) ve Bilgi Bankası makale listesi.
    Dinamik Category modeli üzerinden kategori bazlı filtreleme ve sayaç sunar.
    """
    q = request.GET.get('q', '').strip()
    selected_category = request.GET.get('category', '').strip()

    articles = KnowledgeBaseArticle.objects.filter(is_published=True).select_related('category')

    if q:
        articles = articles.filter(
            Q(title__icontains=q) | 
            Q(content__icontains=q) | 
            Q(keywords__icontains=q)
        )

    if selected_category:
        if selected_category.isdigit():
            articles = articles.filter(category_id=int(selected_category))
        else:
            articles = articles.filter(category__name__icontains=selected_category)

    # Dinamik Kategori istatistikleri (Yayınlanmış makalesi olan kategoriler)
    categories = Category.objects.annotate(
        article_count=Count('kb_articles', filter=Q(kb_articles__is_published=True))
    ).filter(article_count__gt=0).order_by('name')

    categories_stats = [
        {
            'code': str(cat.id),
            'id': cat.id,
            'name': cat.name,
            'count': cat.article_count,
        }
        for cat in categories
    ]

    paginator = Paginator(articles, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'articles': page_obj,
        'categories_stats': categories_stats,
        'search_query': q,
        'selected_category': selected_category,
    }
    return render(request, 'tickets/knowledge_base.html', context)




def knowledge_base_detail_view(request, pk):
    """
    Tek bir Bilgi Bankası makalesinin detay sayfası.
    """
    article = get_object_or_404(KnowledgeBaseArticle.objects.select_related('category'), pk=pk, is_published=True)
    # Görüntülenme sayacını atomik olarak artır (Race condition engellendi)
    KnowledgeBaseArticle.objects.filter(pk=pk).update(views_count=F('views_count') + 1)
    article.refresh_from_db(fields=['views_count'])

    # Benzer / İlgili makaleler
    if article.category:
        related_articles = KnowledgeBaseArticle.objects.filter(
            is_published=True, category=article.category
        ).exclude(pk=article.pk)[:4]
    else:
        related_articles = KnowledgeBaseArticle.objects.filter(
            is_published=True
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
    ).select_related('category').filter(
        Q(title__icontains=q) | Q(keywords__icontains=q) | Q(content__icontains=q)
    )[:4]

    for item in kb_qs:
        suggestions.append({
            'id': item.id,
            'title': item.title,
            'category': item.category.name if item.category else 'Genel',
            'snippet': (item.content[:120] + '...') if len(item.content) > 120 else item.content,
            'url': reverse('knowledge_base_detail', kwargs={'pk': item.id}),
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
            'url': reverse('ticket_detail', kwargs={'pk': t.id}),
            'type': 'ticket',
            'type_display': '✅ Çözülmüş Topluluk Talebi'
        })

    return JsonResponse({'suggestions': suggestions})



