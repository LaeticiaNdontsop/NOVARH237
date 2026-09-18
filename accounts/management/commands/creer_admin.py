"""
Commande de bootstrap : cree le tout premier compte Administrateur de la plateforme.
RG-03 : l'Administrateur est responsable de la creation des autres comptes ;
il faut donc un moyen de creer LE PREMIER compte Admin avant que quiconque
puisse se connecter. `createsuperuser` standard ne renseigne pas le champ `role`
(il resterait a EMPLOYE par defaut), d'ou cette commande dediee.

Usage :
    python manage.py creer_admin --username admin --email admin@novarh.cm --password ChangeMoi123
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role


class Command(BaseCommand):
    help = "Cree le premier compte Administrateur de NOVA RH."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--prenom", default="Admin")
        parser.add_argument("--nom", default="NOVA RH")

    def handle(self, *args, **options):
        Utilisateur = get_user_model()

        if Utilisateur.objects.filter(username=options["username"]).exists():
            raise CommandError(f"Le compte '{options['username']}' existe deja.")

        utilisateur = Utilisateur.objects.create_superuser(
            username=options["username"],
            email=options["email"],
            password=options["password"],
            first_name=options["prenom"],
            last_name=options["nom"],
        )
        utilisateur.role = Role.ADMIN
        utilisateur.doit_changer_mot_de_passe = False
        utilisateur.save(update_fields=["role", "doit_changer_mot_de_passe"])

        self.stdout.write(self.style.SUCCESS(
            f"Compte Administrateur '{utilisateur.username}' cree avec succes."
        ))
