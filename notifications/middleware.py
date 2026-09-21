from .models import definir_requete_courante


class RequeteCouranteMiddleware:
    """Rend la requete courante disponible a `log_activity` (adresse IP, navigateur)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        definir_requete_courante(request)
        try:
            return self.get_response(request)
        finally:
            definir_requete_courante(None)
