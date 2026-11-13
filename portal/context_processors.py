"""Context processor — ცვლადები, რომლებიც ხელმისაწვდომია ყველა შაბლონში.

ჩართულია settings.py-ში: TEMPLATES -> OPTIONS -> context_processors.
ამის წყალობით ყოველ view-ში ცალკე გადაცემა არ გვჭირდება.
"""
from django.conf import settings


def site(request):
    """საიტის სახელი ({{ site_name }}) და წაუკითხავი შეტყობინებების რაოდენობა ({{ unread_count }}) — 🔔-სთვის."""
    context = {"site_name": settings.SITE_NAME}
    if request.user.is_authenticated:
        context["unread_count"] = request.user.notifications.filter(is_read=False).count()
    return context