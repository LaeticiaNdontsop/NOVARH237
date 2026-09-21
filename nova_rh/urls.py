from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("comptes/", include("accounts.urls")),
    path("employes/", include("employees.urls")),
    path("demandes/", include("demandes.urls")),
    path("analytics/", include("analytics.urls")),
    path("notifications/", include("notifications.urls")),
]

if settings.DEBUG:
    # Les medias ne sont PAS servis ici : ils passent par core.views.MediaProtegeView (RG-12).
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
