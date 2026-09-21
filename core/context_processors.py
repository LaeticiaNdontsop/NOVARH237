from django.conf import settings


def coquille(request):
    """Elements communs du cadre (menu, barre du haut) : cloche, droits de lecture, bloc entreprise."""
    contexte = {
        "NOM_ENTREPRISE": settings.NOM_ENTREPRISE,
        "VILLE_ENTREPRISE": settings.VILLE_ENTREPRISE,
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from notifications.views import notifications_recues

        contexte["nb_notifications_non_lues"] = notifications_recues(user).filter(lu=False).count()
        contexte["peut"] = {module: acces["lecture"] for module, acces in user.droits().items()}
    return contexte
