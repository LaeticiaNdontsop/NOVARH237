from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("employe/", include("core.urls_employe")),
    path("employe/", include("employees.urls_employe")),
    path("employe/", include("demandes.urls_employe")),
    path("responsable-rh/", include("core.urls_rh")),
    path("responsable-rh/", include("employees.urls_rh")),
    path("responsable-rh/", include("demandes.urls_rh")),
    path("responsable-rh/", include("analytics.urls_rh")),
    path("administrateur/", include("core.urls_admin")),
    path("administrateur/", include("accounts.urls_admin")),
    path("administrateur/", include("employees.urls_admin")),
    path("administrateur/", include("demandes.urls_admin")),
    path("administrateur/", include("notifications.urls_admin")),
    path("comptes/", include("accounts.urls")),
    path("notifications/", include("notifications.urls")),
]

if settings.DEBUG:
    # Les medias ne sont PAS servis ici : ils passent par core.views.MediaProtegeView (RG-12).
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
