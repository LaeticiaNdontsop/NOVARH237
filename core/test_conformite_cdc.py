"""
Tests de conformite au cahier des charges v6 : droits par role (RG-05, RG-12),
circuit d'evaluation (RG-18), ciblage des formations (RG-23), et RH ne traitant
jamais ses propres demandes.

Lancer en local SANS toucher a la base distante :
    DATABASE_URL="" python manage.py test
"""
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Formation, ParticipationFormation, StatutParticipation
from demandes.models import DemandeConge, Demission, StatutDemande
from employees.models import Document, Employe, TypeDocument
from notifications.models import Notification

User = get_user_model()


def creer_utilisateur(username, role, **extra):
    return User.objects.create_user(
        username=username, password="motdepasse123", role=role,
        first_name=username.capitalize(), last_name="Test", doit_changer_mot_de_passe=False, **extra,
    )


def creer_fiche(user, matricule, service="Administration"):
    return Employe.objects.create(
        utilisateur=user, matricule=matricule, poste="Poste", service=service,
        date_embauche=date(2024, 1, 1),
    )


class BaseCDCTest(TestCase):
    def setUp(self):
        self.admin = creer_utilisateur("admin", "ADMIN")
        self.rh = creer_utilisateur("rh", "RH")
        self.rh2 = creer_utilisateur("rh2", "RH")
        self.emp_user = creer_utilisateur("emp", "EMPLOYE")
        self.autre_user = creer_utilisateur("autre", "EMPLOYE")
        self.fiche_rh = creer_fiche(self.rh, "RH-1", "RH")
        self.fiche_rh2 = creer_fiche(self.rh2, "RH-2", "RH")
        self.emp = creer_fiche(self.emp_user, "E-1")
        self.autre = creer_fiche(self.autre_user, "E-2")


# ---------------------------------------------------------------------------
# RG-05 / RG-12 : documents et fichiers
# ---------------------------------------------------------------------------
class DocumentsEtFichiersTest(BaseCDCTest):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.doc = Document.objects.create(
            employe=self.emp, type_document=TypeDocument.CNI,
            fichier=SimpleUploadedFile("cni.pdf", b"contenu confidentiel"), ajoute_par=self.emp_user,
        )

    def test_rh_ne_peut_pas_ouvrir_le_document_d_un_autre_employe(self):
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("employees:document_detail", args=[self.doc.pk])).status_code, 403)

    def test_proprietaire_et_admin_ouvrent_le_document(self):
        for user in (self.emp_user, self.admin):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(reverse("employees:document_detail", args=[self.doc.pk])).status_code, 200
            )

    def test_fichier_media_refuse_aux_anonymes(self):
        response = self.client.get("/media/" + self.doc.fichier.name)
        self.assertEqual(response.status_code, 302)  # redirection vers la connexion

    def test_fichier_media_refuse_au_rh_et_aux_autres_employes(self):
        for user in (self.rh, self.autre_user):
            self.client.force_login(user)
            self.assertEqual(self.client.get("/media/" + self.doc.fichier.name).status_code, 403)

    def test_fichier_media_accessible_au_proprietaire_et_a_l_admin(self):
        for user in (self.emp_user, self.admin):
            self.client.force_login(user)
            response = self.client.get("/media/" + self.doc.fichier.name)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"contenu confidentiel")

    def test_traversee_de_repertoire_refusee(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/media/../db.sqlite3").status_code, 404)


# ---------------------------------------------------------------------------
# Un RH ne traite jamais ses propres demandes
# ---------------------------------------------------------------------------
class RhNeTraitePasSesPropresDemandesTest(BaseCDCTest):
    def demande_conge(self, client_user):
        self.client.force_login(client_user)
        self.client.post(reverse("demandes:creer_demande"), {
            "type_demande": "CONGE", "date_debut": "2026-11-02", "date_fin": "2026-11-06", "motif": "Repos",
        })
        return DemandeConge.objects.latest("pk")

    def test_conge_d_un_rh_va_directement_a_l_administrateur(self):
        demande = self.demande_conge(self.rh)
        self.assertEqual(demande.statut, StatutDemande.EN_ATTENTE_ADMIN)
        self.assertEqual(demande.admin_assigne, self.admin)
        self.assertIsNone(demande.rh_assigne)

    def test_rh_ne_transmet_pas_sa_propre_demission(self):
        demission = Demission.objects.create(employe=self.fiche_rh, date_effective_souhaitee=date(2026, 12, 1))
        self.client.force_login(self.rh)
        response = self.client.post(reverse("demandes:transmettre_demission", args=[demission.pk]))
        self.assertEqual(response.status_code, 404)
        self.client.force_login(self.rh2)
        response = self.client.post(reverse("demandes:transmettre_demission", args=[demission.pk]))
        self.assertEqual(response.status_code, 302)


# ---------------------------------------------------------------------------
# RG-23 : formations ciblees, pas d'inscription libre
# ---------------------------------------------------------------------------
class FormationsCibleesTest(BaseCDCTest):
    def creer_formation(self, cibles):
        self.client.force_login(self.rh)
        self.client.post(reverse("core:creer_formation"), {
            "titre": "Securite", "description": "", "date_formation": (date.today() + timedelta(days=10)).isoformat(),
            "duree_heures": 4, "employes_cibles": [f.pk for f in cibles],
        })
        return Formation.objects.get(titre="Securite")

    def test_employe_ne_voit_que_les_formations_qui_lui_sont_assignees(self):
        self.creer_formation([self.emp])
        self.client.force_login(self.emp_user)
        self.assertContains(self.client.get(reverse("employees:mes_formations")), "Securite")
        self.client.force_login(self.autre_user)
        self.assertNotContains(self.client.get(reverse("employees:mes_formations")), "Securite")

    def test_employe_cible_est_notifie(self):
        self.creer_formation([self.emp])
        self.assertTrue(Notification.objects.filter(destinataire=self.emp_user, message__contains="Securite").exists())

    def test_suivi_de_participation_par_le_rh(self):
        formation = self.creer_formation([self.emp, self.autre])
        participation = ParticipationFormation.objects.get(formation=formation, employe=self.emp)
        self.assertEqual(participation.statut, StatutParticipation.CIBLE)
        self.client.force_login(self.rh)
        self.client.post(reverse("core:suivi_formation", args=[formation.pk]), {
            f"statut_{participation.pk}": "PARTICIPE",
        })
        participation.refresh_from_db()
        self.assertEqual(participation.statut, StatutParticipation.PARTICIPE)

    def test_modifier_la_cible_conserve_le_suivi_existant(self):
        formation = self.creer_formation([self.emp, self.autre])
        ParticipationFormation.objects.filter(formation=formation, employe=self.emp).update(statut="PARTICIPE")
        self.client.post(reverse("core:modifier_formation", args=[formation.pk]), {
            "titre": "Securite", "description": "", "date_formation": formation.date_formation.isoformat(),
            "duree_heures": 4, "employes_cibles": [self.emp.pk],
        })
        self.assertEqual(formation.participations.count(), 1)
        self.assertEqual(formation.participations.get().statut, "PARTICIPE")

    def test_employe_ne_peut_pas_cibler_ni_suivre(self):
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(reverse("core:creer_formation")).status_code, 403)
        formation = Formation.objects.create(titre="X", date_formation=date.today())
        self.assertEqual(self.client.get(reverse("core:suivi_formation", args=[formation.pk])).status_code, 403)


# ---------------------------------------------------------------------------
# Notifications : un message personnel n'est visible que de son destinataire
# ---------------------------------------------------------------------------
class VisibiliteNotificationsTest(BaseCDCTest):
    def test_notification_personnelle_invisible_pour_les_autres(self):
        Notification.objects.create(
            expediteur=self.rh, destinataire=self.emp_user, role_cible="EMPLOYE", message="Message prive"
        )
        self.client.force_login(self.autre_user)
        self.assertNotContains(self.client.get(reverse("notifications:mes_notifications")), "Message prive")
        self.client.force_login(self.emp_user)
        self.assertContains(self.client.get(reverse("notifications:mes_notifications")), "Message prive")


# ---------------------------------------------------------------------------
# Offres et Recrutement (BF-RH-15 / BF-RH-16, RG-10, RG-11)
# ---------------------------------------------------------------------------
from core.models import Candidature, Offre, StatutOffre  # noqa: E402


class RecrutementTest(BaseCDCTest):
    def creer_offre(self, **extra):
        donnees = dict(poste="Comptable", type_contrat="CDI", lieu="Douala", description="Finance", departement="Finance")
        donnees.update(extra)
        return Offre.objects.create(**donnees)

    def test_crud_complet_des_offres(self):
        self.client.force_login(self.rh)
        self.client.post(reverse("core:creer_offre"), {
            "poste": "Comptable", "departement": "Finance", "type_contrat": "CDI", "lieu": "Douala",
            "description": "Finance", "statut": "PUBLIEE", "responsable": self.rh.pk,
        })
        offre = Offre.objects.get(poste="Comptable")
        self.assertEqual(offre.creee_par, self.rh)

        self.client.post(reverse("core:modifier_offre", args=[offre.pk]), {
            "poste": "Comptable senior", "departement": "Finance", "type_contrat": "CDI", "lieu": "Douala",
            "description": "Finance", "statut": "PUBLIEE",
        })
        offre.refresh_from_db()
        self.assertEqual(offre.poste, "Comptable senior")

        self.assertContains(self.client.get(reverse("core:supprimer_offre", args=[offre.pk])), "Comptable senior")
        self.client.post(reverse("core:supprimer_offre", args=[offre.pk]))
        self.assertFalse(Offre.objects.exists())

    def test_employe_n_accede_ni_aux_offres_ni_au_recrutement(self):
        self.client.force_login(self.emp_user)
        for route in ("core:offres", "core:recrutements", "core:creer_offre"):
            self.assertEqual(self.client.get(reverse(route)).status_code, 403, route)

    def test_le_personnel_saisit_une_candidature_externe_sans_creer_de_compte(self):
        offre = self.creer_offre(statut=StatutOffre.PUBLIEE)
        nb_users = User.objects.count()
        self.client.force_login(self.rh)
        self.client.post(reverse("core:ajouter_candidature", args=[offre.pk]), {
            "nom_candidat": "Paul Externe", "email": "paul@example.com", "telephone": "690000000",
        })
        candidature = Candidature.objects.get(offre=offre)
        self.assertEqual(candidature.saisie_par, self.rh)
        self.assertFalse(candidature.recrute)
        self.assertEqual(User.objects.count(), nb_users)  # RG-11

    def test_suivi_par_etape_entretien_puis_recrutement(self):
        offre = self.creer_offre(statut=StatutOffre.PUBLIEE)
        candidature = Candidature.objects.create(offre=offre, nom_candidat="Paul", email="p@example.com")
        self.client.force_login(self.rh)

        self.client.post(reverse("core:modifier_statut_candidature", args=[candidature.pk]), {
            "statut": "ENTRETIEN", "date_entretien": "2026-10-05T09:30",
        })
        candidature.refresh_from_db()
        self.assertEqual(candidature.statut, "ENTRETIEN")
        self.assertEqual(timezone.localtime(candidature.date_entretien).hour, 9)
        self.assertEqual(Offre.objects.get(pk=offre.pk).etape, "Entretien")

        self.client.post(reverse("core:recruter_candidat", args=[candidature.pk]))
        candidature.refresh_from_db()
        self.assertTrue(candidature.recrute)
        self.assertIsNotNone(candidature.date_recrutement)
        self.assertEqual(Offre.objects.get(pk=offre.pk).etape, "Recrutement finalisé")

    def test_candidature_rejetee_ne_peut_pas_etre_recrutee(self):
        offre = self.creer_offre()
        candidature = Candidature.objects.create(offre=offre, nom_candidat="Paul", email="p@example.com", statut="REJETEE")
        self.client.force_login(self.rh)
        self.client.post(reverse("core:recruter_candidat", args=[candidature.pk]))
        candidature.refresh_from_db()
        self.assertFalse(candidature.recrute)

    def test_tableau_de_bord_compteurs_et_filtres(self):
        finance = self.creer_offre(statut=StatutOffre.PUBLIEE)
        rh = self.creer_offre(poste="Assistant RH", departement="RH", statut=StatutOffre.BROUILLON)
        Candidature.objects.create(offre=finance, nom_candidat="A", email="a@example.com", statut="ENTRETIEN")
        Candidature.objects.create(offre=finance, nom_candidat="B", email="b@example.com")
        self.client.force_login(self.rh)

        response = self.client.get(reverse("core:recrutements"))
        self.assertEqual(response.context["nb_recrutements_en_cours"], 1)
        self.assertEqual(response.context["nb_candidatures"], 2)
        self.assertEqual(response.context["nb_entretiens"], 1)
        self.assertEqual(len(response.context["offres"]), 2)

        response = self.client.get(reverse("core:recrutements"), {"departement": "RH"})
        self.assertEqual([o.pk for o in response.context["offres"]], [rh.pk])
        response = self.client.get(reverse("core:recrutements"), {"etape": "Entretien"})
        self.assertEqual([o.pk for o in response.context["offres"]], [finance.pk])
        response = self.client.get(reverse("core:recrutements"), {"statut": "BROUILLON"})
        self.assertEqual([o.pk for o in response.context["offres"]], [rh.pk])

    def test_cv_des_candidats_reserve_au_personnel_rh_et_admin(self):
        offre = self.creer_offre()
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media):
            c = Candidature.objects.create(
                offre=offre, nom_candidat="Paul", email="p@example.com",
                cv=SimpleUploadedFile("cv.pdf", b"cv"),
            )
            for user, attendu in ((self.emp_user, 403), (self.rh, 200), (self.admin, 200)):
                self.client.force_login(user)
                self.assertEqual(self.client.get("/media/" + c.cv.name).status_code, attendu)
