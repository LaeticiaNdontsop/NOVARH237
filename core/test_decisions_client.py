"""
Tests des decisions du client : circuit des demandes (alertes a 5 h, RH -> Administrateur direct),
droits d'acces par utilisateur, comptes, journal, notifications, absences, analyse, et liens du site.

    DATABASE_URL="" python manage.py test
"""
import re
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import DroitUtilisateur
from demandes.models import Absence, DemandeConge, StatutDemande, reaffecter_demandes_expirees
from employees.models import Employe
from notifications.models import ActivityLog, Notification

User = get_user_model()


def utilisateur(username, role, **extra):
    return User.objects.create_user(
        username=username, password="motdepasse123", role=role, first_name=username.capitalize(),
        last_name="Test", email=f"{username}@exemple.cm", doit_changer_mot_de_passe=False, **extra,
    )


def fiche(user, matricule, service="Administration"):
    return Employe.objects.create(
        utilisateur=user, matricule=matricule, poste="Poste", service=service, date_embauche=date(2024, 1, 1),
    )


class Base(TestCase):
    def setUp(self):
        self.admin = utilisateur("admin", "ADMIN")
        self.rh = utilisateur("rh", "RH")
        self.emp_user = utilisateur("emp", "EMPLOYE")
        self.autre_user = utilisateur("autre", "EMPLOYE")
        self.fiche_rh = fiche(self.rh, "RH-1", "RH")
        self.emp = fiche(self.emp_user, "E-1")
        self.autre = fiche(self.autre_user, "E-2")

    def se_connecter(self, user):
        self.client.force_login(user)


# ---------------------------------------------------------------------------
# Circuit des demandes : alertes a 5 h et demande d'un RH
# ---------------------------------------------------------------------------
class CircuitDemandesTest(Base):
    def demande_employe(self):
        return DemandeConge.objects.create(
            employe=self.emp, type_demande="CONGE", date_debut=date(2026, 11, 2), date_fin=date(2026, 11, 4),
            motif="Repos", rh_assigne=self.rh, date_limite_rh=timezone.now() + timedelta(hours=24),
        )

    def test_alerte_au_rh_apres_5_heures_sans_transmission(self):
        demande = self.demande_employe()
        DemandeConge.objects.filter(pk=demande.pk).update(date_soumission=timezone.now() - timedelta(hours=6))
        reaffecter_demandes_expirees()
        alertes = Notification.objects.filter(destinataire=self.rh, message__startswith="ALERTE")
        self.assertEqual(alertes.count(), 1)
        reaffecter_demandes_expirees()  # pas de doublon
        self.assertEqual(alertes.count(), 1)

    def test_pas_d_alerte_avant_5_heures(self):
        self.demande_employe()
        reaffecter_demandes_expirees()
        self.assertFalse(Notification.objects.filter(message__startswith="ALERTE").exists())

    def test_l_employe_voit_la_decision_si_le_rh_ne_la_communique_pas_en_5_heures(self):
        demande = self.demande_employe()
        DemandeConge.objects.filter(pk=demande.pk).update(
            statut=StatutDemande.APPROUVEE_A_NOTIFIER, admin_traitant=self.admin,
            date_decision_admin=timezone.now() - timedelta(hours=6),
            date_limite_notification=timezone.now() + timedelta(hours=18),
        )
        demande.refresh_from_db()
        self.assertEqual(demande.couleur_employe, "vert")
        self.assertEqual(demande.statut_employe_display, "Approuvee")
        # Le RH, lui, voit toujours l'etape reelle (a communiquer)
        self.assertEqual(demande.couleur, "orange")

        self.se_connecter(self.emp_user)
        self.assertContains(self.client.get(reverse("demandes:mes_demandes")), "Approuvee")

        reaffecter_demandes_expirees()
        self.assertTrue(Notification.objects.filter(destinataire=self.rh, message__startswith="ALERTE").exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.emp_user, message__contains="approuvee").exists())

    def test_decision_recente_reste_orange_pour_l_employe(self):
        demande = self.demande_employe()
        DemandeConge.objects.filter(pk=demande.pk).update(
            statut=StatutDemande.APPROUVEE_A_NOTIFIER, date_decision_admin=timezone.now() - timedelta(hours=1))
        demande.refresh_from_db()
        self.assertEqual(demande.couleur_employe, "orange")

    def test_la_demande_d_un_rh_est_visible_par_l_administrateur_et_sa_decision_est_finale(self):
        self.se_connecter(self.rh)
        self.client.post(reverse("demandes:creer_demande"), {
            "type_demande": "CONGE", "date_debut": "2026-12-01", "date_fin": "2026-12-05", "motif": "Repos"})
        demande = DemandeConge.objects.get(employe=self.fiche_rh)
        self.assertEqual(demande.statut, StatutDemande.EN_ATTENTE_ADMIN)
        self.assertTrue(Notification.objects.filter(destinataire=self.admin, message__contains=demande.reference).exists())

        self.se_connecter(self.admin)
        self.assertContains(self.client.get(reverse("demandes:admin_a_decider")), demande.reference)
        self.client.post(reverse("demandes:approuver_par_admin", args=[demande.pk]), {"commentaire": "OK"})
        demande.refresh_from_db()
        self.assertEqual(demande.statut, StatutDemande.APPROUVEE)  # aucune etape RH pour une demande de RH
        self.assertTrue(Notification.objects.filter(destinataire=self.rh, message__contains="approuvee").exists())

    def test_circuit_complet_employe_rh_admin_rh(self):
        self.se_connecter(self.emp_user)
        self.client.post(reverse("demandes:creer_demande"), {
            "type_demande": "PERMISSION", "date_debut": "2026-12-01", "date_fin": "2026-12-01", "motif": "RDV"})
        demande = DemandeConge.objects.get(employe=self.emp)
        self.assertEqual(demande.rh_assigne, self.rh)

        self.se_connecter(self.rh)
        self.assertContains(self.client.get(reverse("demandes:rh_demandes")), "Traiter")
        self.client.post(reverse("demandes:transmettre_a_admin", args=[demande.pk]), {"commentaire": "RAS"})
        demande.refresh_from_db()
        self.assertEqual(demande.statut, StatutDemande.EN_ATTENTE_ADMIN)

        self.se_connecter(self.admin)
        self.client.post(reverse("demandes:approuver_par_admin", args=[demande.pk]))
        demande.refresh_from_db()
        self.assertEqual(demande.statut, StatutDemande.APPROUVEE_A_NOTIFIER)

        self.se_connecter(self.rh)
        self.client.post(reverse("demandes:cloturer_demande", args=[demande.pk]))
        demande.refresh_from_db()
        self.assertEqual(demande.statut, StatutDemande.APPROUVEE)

    def test_piece_jointe_valide(self):
        self.se_connecter(self.emp_user)
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media):
            mauvais = self.client.post(reverse("demandes:creer_demande"), {
                "type_demande": "CONGE", "date_debut": "2026-12-01", "date_fin": "2026-12-02", "motif": "x",
                "piece_jointe": SimpleUploadedFile("virus.exe", b"MZ")})
            self.assertEqual(mauvais.status_code, 200)
            self.assertFalse(DemandeConge.objects.exists())
            bon = self.client.post(reverse("demandes:creer_demande"), {
                "type_demande": "CONGE", "date_debut": "2026-12-01", "date_fin": "2026-12-02", "motif": "x",
                "commentaire": "Joignable", "piece_jointe": SimpleUploadedFile("attestation.pdf", b"%PDF")})
            self.assertEqual(bon.status_code, 302)
            self.assertTrue(DemandeConge.objects.get().piece_jointe.name.endswith(".pdf"))


# ---------------------------------------------------------------------------
# Absences : déclarations informatives et justificatifs
# ---------------------------------------------------------------------------
class AbsencesTest(Base):
    def test_declaration_avec_justificatif_sans_validation(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media):
            self.se_connecter(self.emp_user)
            reponse = self.client.post(reverse("demandes:creer_absence"), {
                "date_debut": "2026-11-02", "date_fin": "2026-11-03", "type_absence": "MALADIE",
                "motif": "Palu", "justificatif": SimpleUploadedFile("certificat.pdf", b"%PDF")})
            self.assertEqual(reponse.status_code, 302)
            absence = Absence.objects.get()
            self.assertEqual(absence.type_absence, "MALADIE")
            self.assertEqual(absence.statut, "DECLAREE")
            self.assertTrue(absence.justificatif.name.endswith(".pdf"))
            self.assertTrue(Notification.objects.filter(destinataire=self.rh, message__contains="Absence").exists())

            self.se_connecter(self.rh)
            suivi = self.client.get(reverse("demandes:rh_absences"))
            self.assertContains(suivi, "Maladie")
            self.assertNotContains(suivi, "Valider")
            self.assertNotContains(suivi, "Refuser")
            absence.refresh_from_db()
            self.assertEqual(absence.statut, "DECLAREE")

    def test_justificatif_invalide_refuse(self):
        self.se_connecter(self.emp_user)
        reponse = self.client.post(reverse("demandes:creer_absence"), {
            "date_debut": "2026-11-02", "date_fin": "2026-11-03", "type_absence": "AUTRE",
            "justificatif": SimpleUploadedFile("script.sh", b"#!/bin/sh")})
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Absence.objects.exists())

    def test_l_administrateur_consulte_la_declaration_d_un_rh_sans_la_traiter(self):
        absence = Absence.objects.create(employe=self.fiche_rh, date_debut=date(2026, 11, 2), date_fin=date(2026, 11, 2))
        self.se_connecter(self.admin)
        suivi = self.client.get(reverse("demandes:rh_absences"))
        self.assertContains(suivi, "Déclarée")
        self.assertNotContains(suivi, "Valider")
        self.assertNotContains(suivi, "Refuser")
        absence.refresh_from_db()
        self.assertEqual(absence.statut, "DECLAREE")


# ---------------------------------------------------------------------------
# Droits d'acces par utilisateur : attribuer, revoquer, enregistrer
# ---------------------------------------------------------------------------
class DroitsAccesTest(Base):
    def enregistrer(self, cible, cases):
        donnees = {"utilisateur": cible.pk}
        donnees.update({case: "on" for case in cases})
        return self.client.post(reverse("accounts:droits_acces"), donnees)

    def test_seul_l_administrateur_gere_les_droits(self):
        self.se_connecter(self.rh)
        self.assertEqual(self.client.get(reverse("accounts:droits_acces")).status_code, 403)
        self.se_connecter(self.emp_user)
        self.assertEqual(self.client.post(reverse("accounts:droits_acces"), {"utilisateur": self.emp_user.pk,
                                                                             "employes__lecture": "on"}).status_code, 403)

    def test_droits_par_defaut_des_roles(self):
        self.assertTrue(self.rh.a_droit("recrutements", "creation"))
        self.assertFalse(self.rh.a_droit("utilisateurs", "lecture"))
        self.assertFalse(self.emp_user.a_droit("employes", "lecture"))
        self.assertTrue(self.admin.a_droit("utilisateurs", "suppression"))

    def test_attribuer_un_droit_a_un_employe_puis_le_revoquer(self):
        self.se_connecter(self.emp_user)
        self.assertEqual(self.client.get(reverse("employees:liste_employes")).status_code, 403)

        self.se_connecter(self.admin)
        self.enregistrer(self.emp_user, ["employes__lecture", "dashboard__lecture", "assistant__lecture",
                                         "notifications__lecture"])
        self.assertTrue(DroitUtilisateur.objects.filter(utilisateur=self.emp_user, module="employes").exists())

        self.se_connecter(self.emp_user)
        self.assertEqual(self.client.get(reverse("employees:liste_employes")).status_code, 200)
        self.assertEqual(self.client.get(reverse("employees:creer_employe")).status_code, 403)  # pas de creation
        self.assertContains(self.client.get(reverse("core:dashboard_employe")), "Employés")  # menu mis a jour

        self.se_connecter(self.admin)
        self.client.post(reverse("accounts:droits_acces"), {"utilisateur": self.emp_user.pk, "reinitialiser": "1"})
        self.assertFalse(DroitUtilisateur.objects.filter(utilisateur=self.emp_user).exists())
        self.se_connecter(self.emp_user)
        self.assertEqual(self.client.get(reverse("employees:liste_employes")).status_code, 403)

    def test_revoquer_un_droit_par_defaut_du_rh(self):
        self.se_connecter(self.rh)
        self.assertEqual(self.client.get(reverse("core:recrutements")).status_code, 200)
        defauts_rh = ["dashboard__lecture", "employes__lecture", "employes__creation", "employes__modification",
                      "employes__suppression", "demandes__lecture", "demandes__modification", "absences__lecture",
                      "absences__modification", "demissions__lecture", "demissions__modification",
                      "remunerations__lecture", "remunerations__creation", "remunerations__modification",
                      "formations__lecture", "formations__creation", "formations__modification",
                      "analyse__lecture", "assistant__lecture", "notifications__lecture", "notifications__creation"]
        self.se_connecter(self.admin)
        self.enregistrer(self.rh, defauts_rh)  # plus aucun droit sur « recrutements »
        self.se_connecter(self.rh)
        self.assertEqual(self.client.get(reverse("core:recrutements")).status_code, 403)
        self.assertEqual(self.client.get(reverse("employees:liste_employes")).status_code, 200)

    def test_enregistrer_les_droits_par_defaut_ne_cree_aucune_ligne_et_est_journalise(self):
        self.se_connecter(self.admin)
        self.client.post(reverse("accounts:droits_acces"), {"utilisateur": self.emp_user.pk, "dashboard__lecture": "on",
                                                            "assistant__lecture": "on", "notifications__lecture": "on"})
        self.assertFalse(DroitUtilisateur.objects.filter(utilisateur=self.emp_user).exists())
        self.assertTrue(ActivityLog.objects.filter(action="Modification des droits").exists())

    def test_droits_d_un_administrateur_non_modifiables(self):
        self.se_connecter(self.admin)
        self.enregistrer(self.admin, [])
        self.assertFalse(DroitUtilisateur.objects.filter(utilisateur=self.admin).exists())


# ---------------------------------------------------------------------------
# Comptes : creer, modifier, supprimer
# ---------------------------------------------------------------------------
class ComptesTest(Base):
    def test_le_rh_n_accede_pas_a_la_gestion_des_comptes(self):
        self.se_connecter(self.rh)
        self.assertEqual(self.client.get(reverse("accounts:liste_utilisateurs")).status_code, 403)
        self.assertEqual(self.client.post(reverse("accounts:creer_utilisateur"), {}).status_code, 403)

    def test_creer_modifier_supprimer(self):
        self.se_connecter(self.admin)
        reponse = self.client.post(reverse("accounts:creer_utilisateur"), {
            "last_name": "Mavoungou", "first_name": "Arnaud", "email": "arnaud@exemple.cm", "telephone": "670123456",
            "username": "amavoungou", "role": "RH", "is_active": "on", "mot_de_passe_temporaire": "Temporaire#2026"})
        self.assertRedirects(reponse, reverse("accounts:liste_utilisateurs"))
        cree = User.objects.get(username="amavoungou")
        self.assertTrue(cree.doit_changer_mot_de_passe)
        self.assertTrue(cree.check_password("Temporaire#2026"))

        self.client.post(reverse("accounts:modifier_utilisateur", args=[cree.pk]), {
            "last_name": "Mavoungou", "first_name": "Arnaud", "email": "arnaud@exemple.cm", "telephone": "699",
            "role": "EMPLOYE", "is_active": "on"})
        cree.refresh_from_db()
        self.assertEqual(cree.role, "EMPLOYE")

        self.client.post(reverse("accounts:supprimer_utilisateur", args=[cree.pk]))
        self.assertFalse(User.objects.filter(username="amavoungou").exists())

    def test_email_deja_utilise_refuse(self):
        self.se_connecter(self.admin)
        reponse = self.client.post(reverse("accounts:creer_utilisateur"), {
            "last_name": "X", "first_name": "Y", "email": "EMP@exemple.cm", "username": "nouveau", "role": "EMPLOYE",
            "is_active": "on", "mot_de_passe_temporaire": "Temporaire#2026"})
        self.assertContains(reponse, "déjà utilisée")

    def test_suppression_bloquee_pour_un_compte_avec_fiche_ou_pour_soi_meme(self):
        self.se_connecter(self.admin)
        self.client.post(reverse("accounts:supprimer_utilisateur", args=[self.emp_user.pk]))
        self.assertTrue(User.objects.filter(pk=self.emp_user.pk).exists())
        self.client.post(reverse("accounts:supprimer_utilisateur", args=[self.admin.pk]))
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_reinitialisation_du_mot_de_passe_temporaire(self):
        self.se_connecter(self.admin)
        self.client.post(reverse("accounts:reinitialiser_mot_de_passe", args=[self.emp_user.pk]),
                         {"mot_de_passe_temporaire": "Nouveau#2026x"})
        self.emp_user.refresh_from_db()
        self.assertTrue(self.emp_user.check_password("Nouveau#2026x"))
        self.assertTrue(self.emp_user.doit_changer_mot_de_passe)

    def test_filtres_de_la_liste(self):
        self.se_connecter(self.admin)
        reponse = self.client.get(reverse("accounts:liste_utilisateurs"), {"role": "RH"})
        self.assertEqual([u.username for u in reponse.context["utilisateurs"]], ["rh"])
        reponse = self.client.get(reverse("accounts:liste_utilisateurs"), {"q": "autre"})
        self.assertEqual([u.username for u in reponse.context["utilisateurs"]], ["autre"])


# ---------------------------------------------------------------------------
# Journal d'activite
# ---------------------------------------------------------------------------
class JournalTest(Base):
    def test_connexion_reussie_et_echec_sont_journalises_avec_l_ip(self):
        self.client.post(reverse("accounts:login"), {"username": "emp", "password": "faux"},
                         REMOTE_ADDR="192.168.1.33")
        echec = ActivityLog.objects.get(action="Tentative de connexion refusee")
        self.assertEqual(echec.resultat, "ALERTE")
        self.assertEqual(echec.adresse_ip, "192.168.1.33")

        self.client.post(reverse("accounts:login"), {"username": "emp", "password": "motdepasse123"},
                         REMOTE_ADDR="192.168.1.24")
        ok = ActivityLog.objects.get(action="Connexion reussie")
        self.assertEqual(ok.utilisateur, self.emp_user)
        self.assertEqual(ok.adresse_ip, "192.168.1.24")

    def test_journal_reserve_a_l_administrateur_avec_filtres_et_detail(self):
        self.client.post(reverse("accounts:login"), {"username": "ghost", "password": "x"})
        self.se_connecter(self.rh)
        self.assertEqual(self.client.get(reverse("notifications:journal_activite")).status_code, 403)

        self.se_connecter(self.admin)
        reponse = self.client.get(reverse("notifications:journal_activite"))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["nb_alertes_aujourdhui"], 1)
        evenement = ActivityLog.objects.get(action="Tentative de connexion refusee")
        self.assertContains(self.client.get(reverse("notifications:journal_activite"), {"evenement": evenement.pk}),
                            "Détail de l")
        filtre = self.client.get(reverse("notifications:journal_activite"), {"type": "CONNEXION"})
        self.assertTrue(all(e.type_action == "CONNEXION" for e in filtre.context["evenements"]))

    def test_les_actions_sont_journalisees_avec_un_type(self):
        self.se_connecter(self.admin)
        self.client.post(reverse("accounts:creer_utilisateur"), {
            "last_name": "N", "first_name": "M", "email": "nm@exemple.cm", "username": "nm", "role": "EMPLOYE",
            "is_active": "on", "mot_de_passe_temporaire": "Temporaire#2026"})
        journal = ActivityLog.objects.get(action="Creation de compte")
        self.assertEqual(journal.type_action, "UTILISATEUR")
        self.assertEqual(journal.utilisateur, self.admin)


# ---------------------------------------------------------------------------
# Notifications : envoi par l'Administrateur ou le RH, lecture, suppression
# ---------------------------------------------------------------------------
class NotificationsTest(Base):
    def test_l_administrateur_envoie_une_notification_a_un_role(self):
        self.se_connecter(self.admin)
        reponse = self.client.post(reverse("notifications:envoyer"), {
            "titre": "Maintenance", "message": "Coupure ce soir", "cible": "EMPLOYE", "categorie": "COMMUNICATION"})
        self.assertRedirects(reponse, reverse("notifications:mes_notifications"))
        self.assertEqual(Notification.objects.filter(titre="Maintenance").count(), 2)  # emp + autre

        self.se_connecter(self.emp_user)
        page = self.client.get(reverse("notifications:mes_notifications"))
        self.assertContains(page, "Maintenance")
        self.assertNotContains(page, "Créer une notification")  # un employe ne peut qu'en recevoir
        self.assertEqual(self.client.post(reverse("notifications:envoyer"), {}).status_code, 403)

    def test_envoi_a_un_departement_et_a_une_personne(self):
        self.se_connecter(self.rh)
        self.client.post(reverse("notifications:envoyer"), {
            "titre": "Dept", "message": "Reunion", "cible": "DEPARTEMENT", "departement": "Administration",
            "categorie": "COMMUNICATION"})
        self.assertEqual(Notification.objects.filter(titre="Dept").count(), 2)
        self.client.post(reverse("notifications:envoyer"), {
            "titre": "Perso", "message": "Bonjour", "cible": "PERSONNE", "destinataire": self.emp_user.pk,
            "categorie": "COMMUNICATION"})
        self.assertEqual(Notification.objects.filter(titre="Perso").count(), 1)

    def test_tout_marquer_lu_supprimer_et_isolement(self):
        n1 = Notification.objects.create(destinataire=self.emp_user, message="Un", role_cible="TOUS")
        Notification.objects.create(destinataire=self.emp_user, message="Deux", role_cible="TOUS")
        autre = Notification.objects.create(destinataire=self.autre_user, message="Prive", role_cible="TOUS")
        self.se_connecter(self.emp_user)
        self.assertEqual(self.client.get(reverse("notifications:mes_notifications")).context["non_lues"], 2)
        self.client.post(reverse("notifications:tout_marquer_lu"))
        self.assertEqual(self.client.get(reverse("notifications:mes_notifications")).context["non_lues"], 0)
        self.client.post(reverse("notifications:supprimer", args=[n1.pk]))
        self.assertFalse(Notification.objects.filter(pk=n1.pk).exists())
        self.assertEqual(self.client.post(reverse("notifications:supprimer", args=[autre.pk])).status_code, 404)
        self.assertTrue(Notification.objects.filter(pk=autre.pk).exists())

    def test_la_cloche_affiche_le_nombre_de_non_lues(self):
        Notification.objects.create(destinataire=self.emp_user, message="Un", role_cible="TOUS")
        self.se_connecter(self.emp_user)
        self.assertEqual(self.client.get(reverse("core:dashboard_employe")).context["nb_notifications_non_lues"], 1)


# ---------------------------------------------------------------------------
# Analyse intelligente et recherche
# ---------------------------------------------------------------------------
class AnalyseEtRechercheTest(Base):
    def test_analyse_par_departement_reservee_aux_droits(self):
        self.se_connecter(self.emp_user)
        self.assertEqual(self.client.get(reverse("analytics:analyse")).status_code, 403)
        self.se_connecter(self.rh)
        reponse = self.client.get(reverse("analytics:analyse"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "aide à la décision")
        self.assertEqual({l["service"] for l in reponse.context["lignes"]}, {"RH", "Administration"})

    def test_le_niveau_de_risque_repose_sur_des_regles_reelles(self):
        Employe.objects.filter(pk=self.autre.pk).update(statut="INACTIF", date_desactivation=timezone.now())
        self.se_connecter(self.rh)
        lignes = self.client.get(reverse("analytics:analyse")).context["lignes"]
        admin_ligne = next(l for l in lignes if l["service"] == "Administration")
        self.assertEqual(admin_ligne["niveau"], "Élevé")  # 1 depart sur un effectif moyen de 1

    def test_recherche_globale_respecte_les_droits(self):
        self.se_connecter(self.emp_user)
        reponse = self.client.get(reverse("core:recherche"), {"q": "Autre"})
        self.assertNotIn("employes", reponse.context["resultats"])
        self.se_connecter(self.rh)
        reponse = self.client.get(reverse("core:recherche"), {"q": "Autre"})
        self.assertEqual([e.pk for e in reponse.context["resultats"]["employes"]], [self.autre.pk])

    def test_un_employe_ne_trouve_que_ses_propres_demandes(self):
        DemandeConge.objects.create(employe=self.autre, type_demande="CONGE", date_debut=date(2026, 11, 2),
                                    date_fin=date(2026, 11, 3), motif="Mariage secret")
        self.se_connecter(self.emp_user)
        reponse = self.client.get(reverse("core:recherche"), {"q": "Mariage"})
        self.assertEqual(len(reponse.context["resultats"]["demandes"]), 0)


# ---------------------------------------------------------------------------
# Liens : toutes les pages du menu et de la page d'accueil repondent
# ---------------------------------------------------------------------------
LIEN = re.compile(r'href="(/[^"#]*)"')


class LiensTest(Base):
    IGNORES = ("/comptes/deconnexion/", "/media/", "/static/", "/admin/")

    def liens(self, html):
        return {l for l in LIEN.findall(html) if not l.startswith(self.IGNORES)}

    def verifier(self, user, pages_de_depart):
        self.se_connecter(user)
        vus, echecs = set(), []
        a_visiter = set(pages_de_depart)
        for _ in range(2):  # deux niveaux : pages de depart puis liens qu'elles contiennent
            suivants = set()
            for url in sorted(a_visiter - vus):
                vus.add(url)
                reponse = self.client.get(url.split("?")[0] + ("?" + url.split("?", 1)[1] if "?" in url else ""))
                if reponse.status_code not in (200, 302):
                    echecs.append((url, reponse.status_code))
                elif reponse.status_code == 200:
                    suivants |= self.liens(reponse.content.decode())
            a_visiter = suivants
        self.assertEqual(echecs, [], f"Liens en erreur pour {user.role} : {echecs}")
        return vus

    def preparer_donnees(self):
        DemandeConge.objects.create(employe=self.emp, type_demande="CONGE", date_debut=date(2026, 11, 2),
                                    date_fin=date(2026, 11, 3), motif="Repos", rh_assigne=self.rh)
        Absence.objects.create(employe=self.emp, date_debut=date(2026, 11, 2), date_fin=date(2026, 11, 2))
        from core.models import Candidature, Formation, Offre, ParticipationFormation
        offre = Offre.objects.create(poste="Comptable", type_contrat="CDI", lieu="Douala", description="x",
                                     departement="Finance", statut="PUBLIEE")
        Candidature.objects.create(offre=offre, nom_candidat="Paul", email="p@exemple.cm")
        formation = Formation.objects.create(titre="Excel", date_formation=date.today() + timedelta(days=3))
        ParticipationFormation.objects.create(formation=formation, employe=self.emp)

    def test_tous_les_liens_du_rh_fonctionnent(self):
        self.preparer_donnees()
        vus = self.verifier(self.rh, ["/tableau-de-bord/", "/tableau-de-bord/rh/"])
        self.assertGreater(len(vus), 18)

    def test_tous_les_liens_de_l_administrateur_fonctionnent(self):
        self.preparer_donnees()
        vus = self.verifier(self.admin, ["/tableau-de-bord/", "/tableau-de-bord/admin/"])
        self.assertGreater(len(vus), 12)

    def test_tous_les_liens_de_l_employe_fonctionnent(self):
        self.preparer_donnees()
        vus = self.verifier(self.emp_user, ["/tableau-de-bord/", "/tableau-de-bord/employe/"])
        self.assertGreater(len(vus), 10)

    def test_page_d_accueil_publique(self):
        reponse = self.client.get("/")
        self.assertEqual(reponse.status_code, 200)
        html = reponse.content.decode()
        self.assertNotIn("KUMBA", html)
        self.assertNotIn("valuation", html)
        for lien in self.liens(html):
            self.assertIn(self.client.get(lien).status_code, (200, 302), lien)
        # Le menu de l'apercu reprend le vrai menu du RH
        for libelle in ("Recrutements", "Offres d'emploi", "Formations", "Analyse intelligente", "Assistant IA"):
            self.assertIn(libelle, html)
