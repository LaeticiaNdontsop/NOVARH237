from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView, TemplateView

from notifications.models import log_activity
from .droits import ACTIONS, CLES_ACTIONS, MODULES, droits_par_defaut
from .forms import (
    ConnexionForm, CreationUtilisateurForm, ModificationUtilisateurForm, MotDePasseTemporaireForm, ProfilForm,
)
from .mixins import AdminRequiredMixin, droit_requis, exiger_droit
from .models import DroitUtilisateur, Role, Utilisateur


class ConnexionView(LoginView):
    """RG-01 : tout acces a la plateforme necessite une authentification."""
    template_name = "registration/login.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


# ---------------------------------------------------------------------------
# Gestion des utilisateurs (BF-ADM01 a BF-ADM03)
# ---------------------------------------------------------------------------
class ListeUtilisateursView(droit_requis("utilisateurs"), ListView):
    """BF-ADM03 : consulter/gerer les comptes existants."""
    model = Utilisateur
    template_name = "accounts/utilisateur_list.html"
    context_object_name = "utilisateurs"
    paginate_by = 10

    def get_queryset(self):
        qs = Utilisateur.objects.all().order_by("-date_creation")
        recherche = self.request.GET.get("q", "").strip()
        if recherche:
            qs = qs.filter(Q(last_name__icontains=recherche) | Q(first_name__icontains=recherche)
                           | Q(email__icontains=recherche) | Q(username__icontains=recherche))
        role = self.request.GET.get("role", "")
        if role in dict(Role.choices):
            qs = qs.filter(role=role)
        statut = self.request.GET.get("statut", "")
        if statut == "actif":
            qs = qs.filter(is_active=True, last_login__isnull=False)
        elif statut == "desactive":
            qs = qs.filter(is_active=False)
        elif statut == "attente":
            qs = qs.filter(is_active=True, last_login__isnull=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recherche"] = self.request.GET.get("q", "")
        ctx["role_filtre"] = self.request.GET.get("role", "")
        ctx["statut_filtre"] = self.request.GET.get("statut", "")
        ctx["roles"] = Role.choices
        ctx["total"] = Utilisateur.objects.count()
        ctx["peut_creer"] = self.request.user.a_droit("utilisateurs", "creation")
        ctx["peut_modifier"] = self.request.user.a_droit("utilisateurs", "modification")
        ctx["peut_supprimer"] = self.request.user.a_droit("utilisateurs", "suppression")
        return ctx


class CreationUtilisateurView(droit_requis("utilisateurs", "creation", "creation"), CreateView):
    """BF-ADM01 + BF-ADM02 : creation de compte avec mot de passe temporaire."""
    model = Utilisateur
    form_class = CreationUtilisateurForm
    template_name = "accounts/utilisateur_form.html"
    success_url = reverse_lazy("accounts:liste_utilisateurs")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            "Creation de compte",
            f"Compte {self.object.get_full_name()} ({self.object.get_role_display()}) cree.",
        )
        messages.success(
            self.request,
            f"Compte créé pour {self.object.get_full_name()} ({self.object.get_role_display()}). "
            "Communiquez-lui son identifiant et son mot de passe temporaire.",
        )
        return response


class ModifierUtilisateurView(droit_requis("utilisateurs", "modification", "modification"), UpdateView):
    model = Utilisateur
    form_class = ModificationUtilisateurForm
    template_name = "accounts/utilisateur_form.html"
    success_url = reverse_lazy("accounts:liste_utilisateurs")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["mode_modification"] = True
        ctx["form_mot_de_passe"] = MotDePasseTemporaireForm()
        return ctx

    def form_valid(self, form):
        cible = self.get_object()
        if cible.pk == self.request.user.pk and (not form.cleaned_data["is_active"]
                                                  or form.cleaned_data["role"] != cible.role):
            form.add_error(None, "Vous ne pouvez pas désactiver votre propre compte ni modifier votre propre rôle.")
            return self.form_invalid(form)
        response = super().form_valid(form)
        self.object.invalider_droits()
        log_activity(
            self.request.user,
            "Modification de compte",
            f"Compte {self.object.get_full_name()} ({self.object.get_role_display()}) modifie.",
        )
        messages.success(self.request, "Compte mis à jour.")
        return response


class ReinitialiserMotDePasseView(droit_requis("utilisateurs", "modification", "modification"), View):
    """BF-ADM02 : attribution d'un nouveau mot de passe temporaire."""

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk)
        form = MotDePasseTemporaireForm(request.POST)
        if form.is_valid():
            utilisateur.set_password(form.cleaned_data["mot_de_passe_temporaire"])
            utilisateur.doit_changer_mot_de_passe = True
            utilisateur.save(update_fields=["password", "doit_changer_mot_de_passe"])
            log_activity(request.user, "Reinitialisation de mot de passe",
                         f"Nouveau mot de passe temporaire attribue a {utilisateur.get_full_name()}.")
            messages.success(request, "Mot de passe temporaire attribué : l'utilisateur devra le changer à sa prochaine connexion.")
        else:
            messages.error(request, "Le mot de passe temporaire doit contenir au moins 8 caractères.")
        return redirect("accounts:modifier_utilisateur", pk=pk)


class SupprimerUtilisateurView(droit_requis("utilisateurs", "lecture", "suppression"), View):
    template_name = "accounts/utilisateur_confirm_delete.html"

    def _motif_refus(self, request, utilisateur):
        if utilisateur.pk == request.user.pk:
            return "Vous ne pouvez pas supprimer votre propre compte."
        if hasattr(utilisateur, "fiche_employe"):
            return ("Ce compte est rattaché à une fiche employé : sa suppression effacerait aussi la fiche "
                    "et son historique. Désactivez plutôt le compte (Modifier > décocher « Compte actif »).")
        if utilisateur.role == Role.ADMIN and not Utilisateur.objects.filter(
                role=Role.ADMIN, is_active=True).exclude(pk=utilisateur.pk).exists():
            return "Impossible de supprimer le dernier Administrateur actif."
        return None

    def get(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk)
        return render(request, self.template_name,
                      {"utilisateur": utilisateur, "motif_refus": self._motif_refus(request, utilisateur)})

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk)
        motif = self._motif_refus(request, utilisateur)
        if motif:
            messages.error(request, motif)
            return redirect("accounts:liste_utilisateurs")
        nom = utilisateur.get_full_name() or utilisateur.username
        utilisateur.delete()
        log_activity(request.user, "Suppression de compte", f"Compte {nom} supprime.")
        messages.success(request, "Compte supprimé.")
        return redirect("accounts:liste_utilisateurs")


# ---------------------------------------------------------------------------
# Droits d'acces : attribuer / revoquer / enregistrer les droits d'un utilisateur
# ---------------------------------------------------------------------------
class DroitsAccesView(AdminRequiredMixin, TemplateView):
    """
    Reserve au role Administrateur (non delegable, pour eviter toute escalade de privileges).
    Les droits personnalises d'un utilisateur remplacent les droits par defaut de son role.
    """
    template_name = "accounts/droits_acces.html"

    def _utilisateur_choisi(self, request):
        pk = request.GET.get("utilisateur") or request.POST.get("utilisateur")
        if pk and str(pk).isdigit():
            return Utilisateur.objects.filter(pk=int(pk)).first()
        return Utilisateur.objects.exclude(role=Role.ADMIN).order_by("last_name").first() \
            or Utilisateur.objects.order_by("last_name").first()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cible = self._utilisateur_choisi(self.request)
        role_filtre = self.request.GET.get("role", "")
        utilisateurs = Utilisateur.objects.order_by("last_name", "first_name")
        if role_filtre in dict(Role.choices):
            utilisateurs = utilisateurs.filter(role=role_filtre)
        lignes = []
        if cible:
            defauts = droits_par_defaut(cible.role)
            effectifs = cible.droits()
            perso = {d.module: d for d in cible.droits_personnalises.all()}
            for cle, libelle in MODULES:
                lignes.append({
                    "cle": cle, "libelle": libelle, "personnalise": cle in perso,
                    "cases": [
                        {"action": a, "libelle": l, "coche": effectifs[cle][a], "defaut": defauts[cle][a]}
                        for a, l in ACTIONS
                    ],
                })
        ctx.update({
            "cible": cible, "lignes": lignes, "actions": ACTIONS, "utilisateurs": utilisateurs,
            "role_filtre": role_filtre,
            "roles": [(valeur, libelle, Utilisateur.objects.filter(role=valeur).count())
                      for valeur, libelle in Role.choices],
            "nb_personnalises": cible.droits_personnalises.count() if cible else 0,
        })
        return ctx

    def post(self, request, *args, **kwargs):
        cible = self._utilisateur_choisi(request)
        if cible is None:
            return redirect("accounts:droits_acces")
        retour = redirect(f"{reverse('accounts:droits_acces')}?utilisateur={cible.pk}")

        if "reinitialiser" in request.POST:
            cible.droits_personnalises.all().delete()
            log_activity(request.user, "Reinitialisation des droits",
                         f"Droits de {cible.get_full_name()} reinitialises (droits du role {cible.get_role_display()}).")
            messages.success(request, "Droits réinitialisés : les droits par défaut du rôle s'appliquent de nouveau.")
            return retour

        if cible.role == Role.ADMIN:
            messages.error(request, "Les droits d'un Administrateur ne sont pas modifiables.")
            return retour

        defauts = droits_par_defaut(cible.role)
        modifies = []
        for cle, libelle in MODULES:
            choisis = {a: (f"{cle}__{a}" in request.POST) for a in CLES_ACTIONS}
            if choisis == defauts[cle]:
                DroitUtilisateur.objects.filter(utilisateur=cible, module=cle).delete()
            else:
                DroitUtilisateur.objects.update_or_create(utilisateur=cible, module=cle, defaults=choisis)
                modifies.append(libelle)
        cible.invalider_droits()
        log_activity(
            request.user, "Modification des droits",
            f"Droits de {cible.get_full_name()} enregistres"
            + (f" (personnalises : {', '.join(modifies)})." if modifies else " (droits par defaut du role)."),
        )
        messages.success(request, "Droits enregistrés.")
        return retour


# ---------------------------------------------------------------------------
# Profil et mot de passe
# ---------------------------------------------------------------------------
class ProfilView(LoginRequiredMixin, UpdateView):
    """BF-EMP02 / BF-ADM07 / BF-RH-22 : chaque utilisateur gere son propre profil."""
    model = Utilisateur
    form_class = ProfilForm
    template_name = "accounts/profil.html"
    success_url = reverse_lazy("accounts:profil")

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["fiche"] = getattr(self.request.user, "fiche_employe", None)
        ctx["edition"] = self.request.GET.get("modifier") == "1" or bool(ctx["form"].errors)
        return ctx

    def form_valid(self, form):
        log_activity(
            self.request.user,
            "Mise a jour du profil",
            f"Profil de {self.request.user.get_full_name() or self.request.user.username} mis a jour.",
        )
        messages.success(self.request, "Profil mis à jour avec succès.")
        return super().form_valid(form)


class ChangerMotDePasseView(LoginRequiredMixin, TemplateView):
    """
    Changement de mot de passe (BF-EMP02), utilise notamment apres l'attribution
    d'un mot de passe temporaire par l'Administrateur (BF-ADM02).
    """
    template_name = "accounts/changer_mot_de_passe.html"

    def get(self, request, *args, **kwargs):
        form = PasswordChangeForm(user=request.user)
        return self.render_to_response({"form": form})

    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            user.doit_changer_mot_de_passe = False
            user.save(update_fields=["doit_changer_mot_de_passe"])
            log_activity(user, "Changement de mot de passe", "Mot de passe modifie par l'utilisateur.")
            messages.success(request, "Mot de passe modifié avec succès.")
            return redirect("core:redirection_dashboard")
        return self.render_to_response({"form": form})
