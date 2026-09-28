from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, reverse
from django.utils.crypto import get_random_string

from employees.models import Employe
from .models import Formation

TEST_PASSWORD = get_random_string(32)


class RoutesPrincipalesTest(SimpleTestCase):
    def test_routes_principales_existent(self):
        for nom in (
            "employees_employe:mes_documents", "employees_employe:mes_formations",
            "employees_rh:liste_remunerations",
            "employees_admin:liste_employes",
            "notifications:mes_notifications", "notifications_admin:journal_activite",
            "core_rh:recrutements", "core_rh:offres", "core_rh:formations", "core:recherche",
            "accounts_admin:droits_acces", "accounts_admin:liste_utilisateurs", "analytics_rh:analyse",
            "demandes_rh:rh_demandes",
        ):
            with self.subTest(nom=nom):
                self.assertIsNotNone(reverse(nom))

    def test_chemins_canoniques_par_role(self):
        chemins = {
            "core_employe:dashboard_employe": "/employe/",
            "demandes_employe:mes_demandes": "/employe/mes-demandes/",
            "employees_employe:mes_documents": "/employe/mes-documents/",
            "core_rh:dashboard_rh": "/responsable-rh/",
            "employees_rh:liste_employes": "/responsable-rh/employes/",
            "demandes_rh:rh_demandes": "/responsable-rh/demandes/",
            "core_rh:recrutements": "/responsable-rh/recrutements/",
            "analytics_rh:analyse": "/responsable-rh/analyse/",
            "core_admin:dashboard_admin": "/administrateur/",
            "accounts_admin:liste_utilisateurs": "/administrateur/utilisateurs/",
            "demandes_admin:admin_a_decider": "/administrateur/demandes/",
            "notifications_admin:journal_activite": "/administrateur/journal/",
        }
        for nom, chemin in chemins.items():
            with self.subTest(nom=nom):
                self.assertEqual(reverse(nom), chemin)

    def test_remuneration_personnelle_n_est_plus_routee(self):
        with self.assertRaises(NoReverseMatch):
            reverse("employees_employe:mes_remunerations")


class FonctionnalitesTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.rh = user_model.objects.create_user(
            "rh.test", TEST_PASSWORD, role="RH", first_name="RH", last_name="Test",
            doit_changer_mot_de_passe=False,
        )
        self.employe_user = user_model.objects.create_user(
            "employe.test", TEST_PASSWORD, role="EMPLOYE", first_name="Employe",
            last_name="Test", doit_changer_mot_de_passe=False,
        )
        self.employe = Employe.objects.create(
            utilisateur=self.employe_user, matricule="EMP-001", poste="Assistant", service="Administration",
            date_embauche=date(2025, 1, 1),
        )

    def test_un_employe_ne_peut_pas_ouvrir_les_routes_admin_canonique(self):
        self.client.force_login(self.employe_user)
        for nom in ("accounts_admin:liste_utilisateurs", "demandes_admin:admin_a_decider"):
            with self.subTest(nom=nom):
                self.assertEqual(self.client.get(reverse(nom)).status_code, 403)

    def test_rh_cree_une_formation_et_l_employe_la_voit(self):
        self.client.force_login(self.rh)
        response = self.client.post(reverse("core_rh:creer_formation"), {
            "titre": "Securite au travail", "description": "Formation annuelle",
            "date_formation": "2026-10-01", "duree_heures": 4, "employes_cibles": [self.employe.pk],
        })
        self.assertRedirects(response, reverse("core_rh:formations"))
        formation = Formation.objects.get(titre="Securite au travail")
        self.assertEqual([p.employe for p in formation.participations.all()], [self.employe])

        self.client.force_login(self.employe_user)
        response = self.client.get(reverse("employees_employe:mes_formations"))
        self.assertContains(response, "Securite au travail")

    def test_administrateur_choisit_le_type_de_contrat_a_la_creation(self):
        from employees.models import Contrat

        admin = get_user_model().objects.create_user(
            "admin.test", TEST_PASSWORD, role="ADMIN", doit_changer_mot_de_passe=False,
        )
        nouvel_employe = get_user_model().objects.create_user(
            "consultant.test", TEST_PASSWORD, role="EMPLOYE",
            first_name="Consultant", last_name="Test", doit_changer_mot_de_passe=False,
        )
        self.client.force_login(admin)
        response = self.client.post(reverse("employees_admin:creer_employe"), {
            "utilisateur": nouvel_employe.pk,
            "matricule": "",
            "poste": "Consultant RH",
            "service": "RH",
            "date_embauche": "2026-09-01",
            "statut": "ACTIF",
            "type_contrat": "PRESTATION",
        })
        self.assertRedirects(response, reverse("employees_admin:liste_employes"))
        fiche = Employe.objects.get(utilisateur=nouvel_employe)
        contrat = Contrat.objects.get(employe=fiche)
        self.assertEqual(contrat.type_contrat, "PRESTATION")

        response = self.client.post(reverse("employees_admin:modifier_employe", args=[fiche.pk]), {
            "utilisateur": nouvel_employe.pk,
            "matricule": fiche.matricule,
            "poste": fiche.poste,
            "service": fiche.service,
            "date_embauche": fiche.date_embauche.isoformat(),
            "statut": fiche.statut,
            "type_contrat": "STAGE",
        })
        self.assertRedirects(response, reverse("employees_admin:liste_employes"))
        contrat.refresh_from_db()
        self.assertEqual(contrat.type_contrat, "STAGE")

    def test_employe_voit_son_contrat_dans_documents(self):
        from employees.models import Contrat

        Contrat.objects.create(
            employe=self.employe, type_contrat="CDI", poste="Assistant", service="Administration",
            salaire=500000, date_debut=date(2025, 1, 1),
        )
        self.client.force_login(self.employe_user)
        response = self.client.get(reverse("employees_employe:mes_documents"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contrat de travail")

    def test_employe_voit_sa_remuneration_dans_son_profil_sans_lien_sidebar(self):
        from employees.models import Remuneration

        Remuneration.objects.create(
            employe=self.employe, salaire_base=450000, primes=50000, date_effective=date(2026, 1, 1),
        )
        self.client.force_login(self.employe_user)
        response = self.client.get(reverse("accounts:profil"))
        self.assertContains(response, "Ma rémunération")
        self.assertContains(response, "******** FCFA")
        self.assertNotContains(response, "450000 FCFA")
        self.assertNotContains(response, "/employe/mes-remunerations/")

    def test_employe_ne_peut_pas_acceder_au_suivi_recrutement(self):
        self.client.force_login(self.employe_user)
        self.assertEqual(self.client.get(reverse("core_rh:recrutements")).status_code, 403)

    def test_le_menu_du_rh_contient_ses_fonctions_et_son_espace_employe(self):
        Employe.objects.create(
            utilisateur=self.rh, matricule="RH-001", poste="Responsable RH", service="RH",
            date_embauche=date(2024, 1, 1),
        )
        self.client.force_login(self.rh)
        response = self.client.get(reverse("core_rh:dashboard_rh"))
        for libelle in ("Recrutements", "Formations", "Mes documents", "Mes formations",
                        "Analyse intelligente", "Assistant IA"):
            self.assertContains(response, libelle)
        self.assertNotContains(response, "Ma rémunération")
        self.assertNotContains(response, "valuation")

    def test_historiques_accessibles(self):
        self.client.force_login(self.rh)
        for route_name in [
            "demandes_rh:historique_conges", "demandes_rh:historique_absences", "demandes_rh:historique_demissions",
            "notifications:historique_notifications", "core_rh:historique_recrutements", "core_rh:historique_formations",
        ]:
            with self.subTest(route_name=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)
