import logging
import time

from .models import reaffecter_demandes_expirees

logger = logging.getLogger(__name__)

INTERVALLE_SECONDES = 60
_derniere_verification = 0.0


class VerificationDelaisMiddleware:
    """
    Declenche, au plus une fois par minute, les alertes a 5 h et les reaffectations
    a 24 h (RG-20 / RG-21), sans dependre d'une tache planifiee. En production, la
    commande `manage.py verifier_delais_demandes` peut aussi etre lancee par cron.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        global _derniere_verification
        if request.user.is_authenticated and time.monotonic() - _derniere_verification > INTERVALLE_SECONDES:
            _derniere_verification = time.monotonic()
            try:
                reaffecter_demandes_expirees()
            except Exception:
                logger.exception("Echec de la verification des delais des demandes")
        return self.get_response(request)
