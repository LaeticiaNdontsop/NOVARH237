from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from employees.models import Employe
from .models import Formation


class RoutesPrincipalesTest(SimpleTestCase):
    def test_routes_principales_existent(self):
        for nom in (
            "employees:mes_documents", "employees:mes_remunerations", "employees:mes_formations",
            "employees:liste_remunerations", "notifications:mes_notifications", "notifications:journal_activite",
            "core:recrutements", "core:offres", "core:formations", "core:recherche",
            "accounts:droits_acces", "accounts:liste_utilisateurs", "analytics:analyse",
            "demandes:rh_demandes",
        ):
            with self.subTest(nom=nom):
                self.assertIsNotNone(reverse(nom))


class FonctionnalitesTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.rh = user_model.objects.create_user(
            username="rh.test", password="motdepasse123", role="RH", first_name="RH", last_name="Test",
            doit_changer_mot_de_passe=False,
        )
        self.employe_user = user_model.objects.create_user(
            username="employe.test", password="motdepasse123", role="EMPLOYE", first_name="Employe",
            last_name="Test", doit_changer_mot_de_passe=False,
        )
        self.employe = Employe.objects.create(
            utilisateur=self.employe_user, matricule="EMP-001", poste="Assistant", service="Administration",
            date_embauche=date(2025, 1, 1),
        )

    def test_rh_cree_une_formation_et_l_employe_la_voit(self):
        self.client.force_login(self.rh)
        response = self.client.post(reverse("core:creer_formation"), {
            "titre": "Securite au travail", "description": "Formation annuelle",
            "date_formation": "2026-10-01", "duree_heures": 4, "employes_cibles": [self.employe.pk],
        })
        self.assertRedirects(response, reverse("core:formations"))
        formation = Formation.objects.get(titre="Securite au travail")
        self.assertEqual([p.employe for p in formation.participations.all()], [self.employe])

        self.client.force_login(self.employe_user)
        response = self.client.get(reverse("employees:mes_formations"))
        self.assertContains(response, "Securite au travail")

    def test_employe_voit_son_contrat_dans_documents(self):
        from employees.models import Contrat

        Contrat.objects.create(
            employe=self.employe, type_contrat="CDI", poste="Assistant", service="Administration",
            salaire=500000, date_debut=date(2025, 1, 1),
        )
        self.client.force_login(self.employe_user)
        response = self.client.get(reverse("employees:mes_documents"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contrat de travail")

    def test_employe_ne_peut_pas_acceder_au_suivi_recrutement(self):
        self.client.force_login(self.employe_user)
        self.assertEqual(self.client.get(reverse("core:recrutements")).status_code, 403)

    def test_le_menu_du_rh_contient_ses_fonctions_et_son_espace_employe(self):
        Employe.objects.create(
            utilisateur=self.rh, matricule="RH-001", poste="Responsable RH", service="RH",
            date_embauche=date(2024, 1, 1),
        )
        self.client.force_login(self.rh)
        response = self.client.get(reverse("core:dashboard_rh"))
        for libelle in ("Recrutements", "Formations", "Mes documents", "Ma rémunération", "Mes formations",
                        "Analyse intelligente", "Assistant IA"):
            self.assertContains(response, libelle)
        self.assertNotContains(response, "valuation")

    def test_historiques_accessibles(self):
        self.client.force_login(self.rh)
        for route_name in [
            "demandes:historique_conges", "demandes:historique_absences", "demandes:historique_demissions",
            "notifications:historique_notifications", "core:historique_recrutements", "core:historique_formations",
        ]:
            with self.subTest(route_name=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)
