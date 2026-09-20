from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from employees.models import Employe
from .models import Candidature, Formation, Offre, StatutOffre


class ModulesManquantsTest(SimpleTestCase):
    def test_routes_principales_exist(self):
        self.assertIsNotNone(reverse("employees:mes_documents"))
        self.assertIsNotNone(reverse("employees:mes_remunerations"))
        self.assertIsNotNone(reverse("employees:mes_evaluations_formations"))
        self.assertIsNotNone(reverse("notifications:mes_notifications"))
        self.assertIsNotNone(reverse("core:recrutements"))
        self.assertIsNotNone(reverse("core:offres"))
        self.assertIsNotNone(reverse("core:roles_droits"))
        self.assertIsNotNone(reverse("core:journal_activite"))


class Jour3FonctionnalitesTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.rh = user_model.objects.create_user(
            username="rh.test", password="motdepasse123", role="RH", first_name="RH", last_name="Test"
        )
        self.employe_user = user_model.objects.create_user(
            username="employe.test", password="motdepasse123", role="EMPLOYE", first_name="Employe", last_name="Test"
        )
        self.employe = Employe.objects.create(
            utilisateur=self.employe_user,
            matricule="EMP-001",
            poste="Assistant",
            service="Administration",
            date_embauche=date(2025, 1, 1),
        )

    def test_rh_cree_une_formation_et_l_employe_la_voit(self):
        self.client.force_login(self.rh)
        response = self.client.post(reverse("core:creer_formation"), {
            "titre": "Securite au travail",
            "description": "Formation annuelle",
            "date_formation": "2026-10-01",
            "duree_heures": 4,
            "participants": [self.employe.pk],
        })
        self.assertRedirects(response, reverse("core:evaluations_formations"))
        formation = Formation.objects.get(titre="Securite au travail")
        self.assertEqual(list(formation.participants.all()), [self.employe])

        self.client.force_login(self.employe_user)
        response = self.client.get(reverse("employees:mes_evaluations_formations"))
        self.assertContains(response, "Securite au travail")

    def test_employe_postule_a_une_offre_publiee(self):
        offre = Offre.objects.create(
            poste="Comptable",
            type_contrat="CDI",
            lieu="Douala",
            description="Rejoindre l equipe finance",
            statut=StatutOffre.PUBLIEE,
        )
        self.client.force_login(self.employe_user)
        response = self.client.post(reverse("core:postuler_offre", args=[offre.pk]), {
            "nom_candidat": "Employe Test",
            "email": "employe@example.com",
            "telephone": "690000000",
        })
        self.assertRedirects(response, reverse("core:offres"))
        self.assertTrue(Candidature.objects.filter(offre=offre, email="employe@example.com").exists())

    def test_employe_voit_son_contrat_dans_documents(self):
        from employees.models import Contrat

        Contrat.objects.create(
            employe=self.employe,
            type_contrat="CDI",
            poste="Assistant",
            service="Administration",
            salaire=500000,
            date_debut=date(2025, 1, 1),
        )

        self.client.force_login(self.employe_user)
        response = self.client.get(reverse("employees:mes_documents"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contrat de travail")

    def test_employe_ne_peut_pas_acceder_au_suivi_recrutement(self):
        self.client.force_login(self.employe_user)
        response = self.client.get(reverse("core:recrutements"))
        self.assertEqual(response.status_code, 403)

    def test_rh_voit_les_fonctionnalites_employe_dans_le_menu(self):
        Employe.objects.create(
            utilisateur=self.rh,
            matricule="RH-001",
            poste="Responsable RH",
            service="RH",
            date_embauche=date(2024, 1, 1),
        )
        self.client.force_login(self.rh)
        response = self.client.get(reverse("core:dashboard_rh"))
        self.assertNotContains(response, "Mon contrat")
        self.assertContains(response, "Mes documents")
        self.assertContains(response, "Mes remunerations")
        self.assertContains(response, "Mes evaluations &amp; formations")

    def test_historique_des_fonctionnalites_est_accessible(self):
        self.client.force_login(self.rh)
        for route_name in [
            "demandes:historique_conges",
            "demandes:historique_absences",
            "demandes:historique_demissions",
            "notifications:historique_notifications",
            "core:historique_recrutements",
            "core:historique_evaluations_formations",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertIn(response.status_code, [200, 302, 403])
