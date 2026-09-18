"""
RG-20 : a chaque etape de transmission du circuit conges/permissions, un delai de
24 heures est accorde ; passe ce delai, reaffectation automatique a un autre
utilisateur du meme role si disponible.
RG-21 : si aucune reaffectation n'est possible, la demande reste en attente
(orange) et une alerte est enregistree (voir modele AlerteSysteme).

Cette commande est concue pour etre executee periodiquement (ex. toutes les
30 minutes) via une tache planifiee (cron, Celery beat...). A defaut d'un tel
planificateur en environnement de demonstration, elle peut aussi etre lancee
manuellement :

    python manage.py verifier_delais_demandes
"""
from django.core.management.base import BaseCommand

from demandes.models import reaffecter_demandes_expirees, AlerteSysteme


class Command(BaseCommand):
    help = "Verifie les delais de 24h du circuit conges/permissions et reaffecte si necessaire (RG-20/RG-21)."

    def handle(self, *args, **options):
        avant = AlerteSysteme.objects.filter(resolue=False).count()
        reaffecter_demandes_expirees()
        apres = AlerteSysteme.objects.filter(resolue=False).count()

        self.stdout.write(self.style.SUCCESS("Verification des delais effectuee."))
        if apres > avant:
            self.stdout.write(self.style.WARNING(
                f"{apres - avant} nouvelle(s) alerte(s) : aucune reaffectation possible pour certaines demandes."
            ))
