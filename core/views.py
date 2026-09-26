import os

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.utils._os import safe_join
from django.views import View
from django.views.generic import TemplateView

from accounts.models import Utilisateur
from analytics import indicateurs
from demandes.models import (
    Absence, DemandeConge, Demission, StatutAbsence, StatutDemande, StatutDemission,
)
from employees.models import Document, Employe, StatutEmploye
from notifications.models import ActivityLog
from notifications.views import notifications_recues
from .models import Formation, Offre, ParticipationFormation


class AccueilView(TemplateView):
    """
    Page d'accueil publique (vitrine). Un utilisateur deja connecte est renvoye
    directement vers son tableau de bord.
    """
    template_name = "core/accueil.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:redirection_dashboard")
        return super().dispatch(request, *args, **kwargs)


class MediaProtegeView(LoginRequiredMixin, View):
    """
    RG-12 : les fichiers uploades (contrats, documents, justificatifs, CV) ne sont
    plus servis publiquement ; chaque acces est controle selon le type de fichier.
    """

    def get(self, request, chemin):
        try:
            chemin_absolu = safe_join(settings.MEDIA_ROOT, chemin)
        except SuspiciousFileOperation:
            raise Http404
        if not os.path.isfile(chemin_absolu):
            raise Http404
        if not self._autorise(request.user, chemin.replace("\\", "/")):
            raise PermissionDenied("Vous ne pouvez pas acceder a ce fichier.")
        return FileResponse(open(chemin_absolu, "rb"))

    @staticmethod
    def _autorise(user, chemin):
        from employees.models import Contrat

        if user.est_admin:
            return True
        if chemin.startswith("photos_profil/"):
            return Utilisateur.objects.filter(photo=chemin).exists()
        if chemin.startswith("documents/"):
            # RG-05 : seul le proprietaire (ou l'Administrateur) consulte un document.
            return Document.objects.filter(fichier=chemin, employe__utilisateur=user).exists()
        if chemin.startswith("contrats/"):
            if user.est_rh:
                return Contrat.objects.filter(fichier_contrat=chemin).exists()
            return Contrat.objects.filter(fichier_contrat=chemin, employe__utilisateur=user).exists()
        if chemin.startswith("justificatifs_absence/"):
            if user.est_rh:
                return Absence.objects.filter(justificatif=chemin).exists()
            return Absence.objects.filter(justificatif=chemin, employe__utilisateur=user).exists()
        if chemin.startswith("demandes_pj/"):
            if user.est_rh:
                return DemandeConge.objects.filter(piece_jointe=chemin).exists()
            return DemandeConge.objects.filter(piece_jointe=chemin, employe__utilisateur=user).exists()
        if chemin.startswith("candidatures/"):
            return user.a_droit("recrutements", "lecture")
        return False


class RedirectionDashboardView(LoginRequiredMixin, View):
    """
    Point d'entree unique apres connexion : redirige vers le tableau de bord
    adapte au role de l'utilisateur (RG-02).
    """
    def get(self, request):
        user = request.user
        if user.doit_changer_mot_de_passe:
            return redirect("accounts:changer_mot_de_passe")
        if user.est_admin:
            return redirect("core:dashboard_admin")
        if user.est_rh:
            return redirect("core:dashboard_rh")
        return redirect("core:dashboard_employe")


def _exiger_role(user, *roles):
    if user.role not in roles:
        raise PermissionDenied("Ce tableau de bord est reserve a un autre role.")


class DashboardAdminView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard_admin.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        _exiger_role(user, "ADMIN")
        aujourdhui = timezone.localdate()
        debut_jour = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)

        utilisateurs = Utilisateur.objects.all()
        total = utilisateurs.count()
        actifs = utilisateurs.filter(is_active=True, last_login__isnull=False).count()
        desactives = utilisateurs.filter(is_active=False).count()
        en_attente = utilisateurs.filter(is_active=True, last_login__isnull=True).count()

        def part(n):
            return round(n / total * 100, 1) if total else 0

        segments, cumul = [], 0.0
        for couleur, n in (("#0b52d9", actifs), ("#f97316", desactives), ("#cbd5e1", en_attente)):
            p = n / total * 100 if total else 0
            segments.append(f"{couleur} {cumul:.2f}% {cumul + p:.2f}%")
            cumul += p

        actions_jour = ActivityLog.objects.filter(date_creation__gte=debut_jour)
        alertes_jour = actions_jour.filter(resultat="ALERTE").count()
        ctx.update({
            "nb_utilisateurs": total,
            "nouveaux_ce_mois": utilisateurs.filter(date_creation__year=aujourdhui.year,
                                                    date_creation__month=aujourdhui.month).count(),
            "nb_roles_actifs": utilisateurs.values("role").distinct().count(),
            "nb_actions_jour": actions_jour.count(),
            "nb_alertes_jour": alertes_jour,
            "comptes": [
                {"libelle": "Actifs", "n": actifs, "pct": part(actifs), "couleur": "#0b52d9"},
                {"libelle": "Désactivés", "n": desactives, "pct": part(desactives), "couleur": "#f97316"},
                {"libelle": "En attente", "n": en_attente, "pct": part(en_attente), "couleur": "#cbd5e1"},
            ],
            "gradient_comptes": "conic-gradient(" + ", ".join(segments) + ")" if total else "none",
            "activite_recente": ActivityLog.objects.select_related("utilisateur")[:5],
            "demandes_a_decider": DemandeConge.objects.filter(statut=StatutDemande.EN_ATTENTE_ADMIN).filter(
                Q(admin_assigne=user) | Q(admin_assigne__isnull=True)).count(),
            "demissions_a_traiter": Demission.objects.filter(statut=StatutDemission.TRANSMISE_ADMIN).count(),
            "absences_rh_declarees": Absence.objects.filter(
                employe__utilisateur__role="RH").count(),
            "effectif_total": Employe.objects.filter(statut=StatutEmploye.ACTIF).count(),
            "turnover_12_mois": indicateurs.turnover(),
        })
        return ctx


class DashboardRHView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard_rh.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        _exiger_role(user, "RH")
        autres_demandes = DemandeConge.objects.exclude(employe__utilisateur=user)
        en_attente = autres_demandes.filter(statut__in=[
            StatutDemande.EN_ATTENTE_RH, StatutDemande.EN_ATTENTE_ADMIN, StatutDemande.APPROUVEE_A_NOTIFIER])
        historique = indicateurs.historique_effectif(6)
        variation = indicateurs.variation_effectif(6)
        absences_courant, absences_precedent = indicateurs.absences_mois_et_precedent()
        variation_absences = None
        if absences_precedent:
            variation_absences = round((absences_courant - absences_precedent) / absences_precedent * 100)
        absences = Absence.objects.exclude(employe__utilisateur=user)
        ctx.update({
            "effectif_total": Employe.objects.filter(statut=StatutEmploye.ACTIF).count(),
            "embauches_du_mois": indicateurs.embauches_du_mois(),
            "nb_recrutements": sum(1 for o in Offre.objects.all() if o.est_active),
            "nb_demandes_attente": en_attente.count(),
            "demandes_a_traiter": autres_demandes.filter(
                statut=StatutDemande.EN_ATTENTE_RH, rh_assigne=user).count(),
            "demandes_a_communiquer": autres_demandes.filter(
                statut=StatutDemande.APPROUVEE_A_NOTIFIER, rh_assigne=user).count(),
            "nb_absences": absences.count(),
            "demissions_en_cours": Demission.objects.exclude(statut=StatutDemission.COMMUNIQUEE).count(),
            "courbe": indicateurs.courbe_svg(historique),
            "repartition": indicateurs.repartition_departements(),
            "demandes_recentes": autres_demandes.select_related("employe__utilisateur")[:5],
            "variation_effectif": variation,
            "delai_moyen": indicateurs.delai_moyen_traitement_jours(),
            "absences_ce_mois": absences_courant,
            "variation_absences": variation_absences,
        })
        ctx["texte_demandes"] = (
            f"{ctx['demandes_a_traiter']} à transmettre · {ctx['demandes_a_communiquer']} à communiquer"
        )
        return ctx


class DashboardEmployeView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard_employe.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        fiche = getattr(user, "fiche_employe", None)
        ctx["fiche"] = fiche
        ctx["notifications_recentes"] = notifications_recues(user).order_by("-date_creation")[:5]
        if fiche is not None:
            demandes = DemandeConge.objects.filter(employe=fiche)
            ctx["demandes_en_cours"] = demandes.exclude(
                statut__in=["APPROUVEE", "REJETEE_RH", "REJETEE_ADMIN"]).count()
            ctx["mes_demandes_recentes"] = demandes[:5]
            ctx["nb_documents"] = Document.objects.filter(employe=fiche).count()
            ctx["nb_absences"] = Absence.objects.filter(employe=fiche).count()
            ctx["nb_formations"] = ParticipationFormation.objects.filter(
                employe=fiche, formation__annulee=False, formation__date_formation__gte=timezone.localdate()).count()
            contrat = fiche.contrats.order_by("-date_debut").first()
            ctx["contrat"] = contrat
        return ctx


class RechercheView(LoginRequiredMixin, TemplateView):
    """
    Recherche globale de la barre du haut. RG-06 : chaque role ne trouve que ce
    qu'il a le droit de consulter (un employe ne voit que ses propres demandes).
    """
    template_name = "core/recherche.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        q = self.request.GET.get("q", "").strip()
        ctx["q"] = q
        resultats = {}
        if len(q) >= 2:
            if user.a_droit("employes", "lecture"):
                resultats["employes"] = Employe.objects.select_related("utilisateur").filter(
                    Q(utilisateur__last_name__icontains=q) | Q(utilisateur__first_name__icontains=q)
                    | Q(matricule__icontains=q) | Q(poste__icontains=q) | Q(service__icontains=q))[:10]
            if user.a_droit("recrutements", "lecture"):
                resultats["offres"] = Offre.objects.filter(
                    Q(poste__icontains=q) | Q(departement__icontains=q) | Q(competences__icontains=q))[:10]
            demandes = DemandeConge.objects.select_related("employe__utilisateur")
            if not user.a_droit("demandes", "lecture"):
                demandes = demandes.filter(employe__utilisateur=user)
            resultats["demandes"] = demandes.filter(
                Q(motif__icontains=q) | Q(employe__utilisateur__last_name__icontains=q)
                | Q(employe__utilisateur__first_name__icontains=q))[:10]
            formations = Formation.objects.filter(Q(titre__icontains=q) | Q(description__icontains=q))
            if not user.a_droit("formations", "lecture"):
                formations = formations.filter(participations__employe__utilisateur=user)
            resultats["formations"] = formations.distinct()[:10]
            if user.a_droit("utilisateurs", "lecture"):
                resultats["utilisateurs"] = Utilisateur.objects.filter(
                    Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(email__icontains=q)
                    | Q(username__icontains=q))[:10]
        ctx["resultats"] = resultats
        ctx["nb_resultats"] = sum(len(v) for v in resultats.values())
        return ctx
